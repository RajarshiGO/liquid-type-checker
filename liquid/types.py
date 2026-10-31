"""
Core type definitions for Liquid Types implementation.

This module defines the base types and type constructors used in the
Hindley-Milner type system extended with refinement types.
"""

from dataclasses import dataclass
from typing import Set, Dict, FrozenSet


class Type:
    """Base class for all types."""
    pass


class Int(Type):
    """Integer type, optionally with a concrete value."""
    
    def __init__(self, value: int | str | None = None) -> None:
        if value is not None:
            try:
                self.value = int(value)
            except ValueError:
                self.value = None
        else:
            self.value = None

    def __repr__(self):
        if self.value is not None:
            return f"{self.value}"
        return f"int"

    def __eq__(self, other):
        if isinstance(other, Int):
            if self.value is None and other.value is None:
                return True
            if self.value is not None and other.value is not None:
                return self.value == other.value
            return False
        return False

    def __hash__(self):
        if self.value is None:
            return hash("int_type")
        return hash(("int_literal", self.value))


class Bool(Type):
    """Boolean type, optionally with a concrete value."""
    
    def __init__(self, value: bool | str | None = None):
        if value is not None:
            if isinstance(value, bool):
                self.value = value
            elif isinstance(value, str):
                if value.lower() == "true":
                    self.value = True
                elif value.lower() == "false":
                    self.value = False
                else:
                    self.value = None
            else:
                self.value = None
        else:
            self.value = None

    def __repr__(self):
        if self.value is not None:
            return f"bool:{self.value}"
        return f"bool"

    def __eq__(self, other):
        if isinstance(other, Bool):
            if self.value is None and other.value is None:
                return True
            if self.value is not None and other.value is not None:
                return self.value == other.value
            return False
        return False

    def __hash__(self):
        if self.value is None:
            return hash("bool_type")
        return hash(("bool_literal", self.value))


class TVar(Type):
    """Type variable for polymorphism."""
    
    next_id = 0

    def __init__(self, name: str = None):
        if name is None:
            self.id = TVar.next_id
            TVar.next_id += 1
            self.name = f"'a{self.id}"
        else:
            self.name = name
            self.id = hash(name)

    def __repr__(self):
        return self.name

    def __eq__(self, other):
        return isinstance(other, TVar) and self.name == other.name

    def __hash__(self):
        return hash(self.name)


class TFun(Type):
    """Function type: param_type -> return_type."""
    
    def __init__(self, param_type: Type, return_type: Type):
        self.param_type = param_type
        self.return_type = return_type

    def __repr__(self):
        param_str = f"({self.param_type})" if isinstance(self.param_type, TFun) else str(self.param_type)
        return f"({param_str} -> {self.return_type})"

    def __eq__(self, other):
        return isinstance(other, TFun) and \
               self.param_type == other.param_type and \
               self.return_type == other.return_type

    def __hash__(self):
        return hash((self.param_type, self.return_type))


class TScheme(Type):
    """Type scheme with universally quantified type variables."""
    
    def __init__(self, bound_vars: Set[TVar], monotype: Type) -> None:
        self.bound_vars = frozenset(bound_vars)
        self.monotype = monotype

    def __repr__(self):
        if not self.bound_vars:
            return str(self.monotype)
        return f"for all {', '.join(sorted(v.name for v in self.bound_vars))}. {self.monotype}"

    def __eq__(self, other):
        return isinstance(other, TScheme) and \
               self.bound_vars == other.bound_vars and \
               self.monotype == other.monotype

    def __hash__(self):
        return hash((self.bound_vars, self.monotype))


@dataclass(frozen=True)
class RefinedType(Type):
    """Refinement type: { base_type | predicate }."""
    base_type: Type
    predicate: 'Predicate'  # Forward reference

    def __str__(self):
        from liquid.predicates import TruePred
        if isinstance(self.predicate, TruePred):
            return str(self.base_type)
        return f"{{ {self.base_type} | {self.predicate} }}"

    def __repr__(self):
        return str(self)


# Type aliases
Substitution = Dict[TVar, Type]
TypeEnv = Dict[str, TScheme]


def free_type_vars(t: Type) -> Set[TVar]:
    """Get all free type variables in a type."""
    if isinstance(t, TVar):
        return {t}
    elif isinstance(t, TFun):
        return free_type_vars(t.param_type).union(free_type_vars(t.return_type))
    elif isinstance(t, RefinedType):
        return free_type_vars(t.base_type)
    elif isinstance(t, (Int, Bool)):
        return set()
    elif isinstance(t, TScheme):
        return free_type_vars_scheme(t)
    raise TypeError(f"Unknown type for free_type_vars: {type(t)}")


def free_type_vars_scheme(scheme: TScheme) -> Set[TVar]:
    """Get free type variables in a type scheme (excluding bound vars)."""
    return free_type_vars(scheme.monotype).difference(scheme.bound_vars)


def generate_fresh_tvar() -> TVar:
    """Generate a fresh type variable."""
    return TVar()


def apply_sub(sub: Substitution, t: Type) -> Type:
    """
    Apply a substitution to a type.
    Ensures that TVar, Int, or Bool types are wrapped in RefinedType.
    """
    if isinstance(t, TVar):
        substituted_val = sub.get(t, t)
        if isinstance(substituted_val, (RefinedType, TFun)):
            return substituted_val
        elif isinstance(substituted_val, (TVar, Int, Bool)):
            from liquid.predicates import TruePred
            return RefinedType(substituted_val, TruePred())
        return substituted_val
    elif isinstance(t, TFun):
        return TFun(apply_sub(sub, t.param_type), apply_sub(sub, t.return_type))
    elif isinstance(t, RefinedType):
        new_base_type = apply_sub(sub, t.base_type)
        return RefinedType(new_base_type, t.predicate)
    elif isinstance(t, Int):
        from liquid.predicates import TruePred
        return RefinedType(t, TruePred())
    elif isinstance(t, Bool):
        from liquid.predicates import TruePred
        return RefinedType(t, TruePred())
    elif isinstance(t, TScheme):
        return TScheme(t.bound_vars, apply_sub(sub, t.monotype))
    return t


def apply_sub_to_env(sub: Substitution, env: TypeEnv) -> TypeEnv:
    """Apply a substitution to all types in an environment."""
    new_env = {}
    for var_name, scheme in env.items():
        new_monotype = apply_sub(sub, scheme.monotype)
        new_env[var_name] = TScheme(scheme.bound_vars, new_monotype)
    return new_env


def compose_subs(s1: Substitution, s2: Substitution) -> Substitution:
    """Compose two substitutions: s1 after s2."""
    new_s = {}
    for k, v in s1.items():
        new_s[k] = apply_sub(s2, v)
    for k, v in s2.items():
        if k not in new_s:
            new_s[k] = v
    return new_s


class UnificationError(Exception):
    """Raised when two types cannot be unified."""
    pass


def unify(t1: Type, t2: Type) -> Substitution:
    """Unify two types, returning a substitution."""
    if t1 == t2:
        return {}

    if isinstance(t1, RefinedType) and isinstance(t2, RefinedType):
        s = unify(t1.base_type, t2.base_type)
        return s

    if isinstance(t1, RefinedType):
        s = unify(t1.base_type, t2)
        return s

    if isinstance(t2, RefinedType):
        s = unify(t1, t2.base_type)
        return s

    if isinstance(t1, TVar):
        return bind(t1, t2)
    if isinstance(t2, TVar):
        return bind(t2, t1)

    if isinstance(t1, TFun) and isinstance(t2, TFun):
        s1 = unify(t1.param_type, t2.param_type)
        s2 = unify(apply_sub(s1, t1.return_type), apply_sub(s1, t2.return_type))
        return compose_subs(s1, s2)

    if isinstance(t1, Int) and isinstance(t2, Int):
        return {}
    if isinstance(t1, Bool) and isinstance(t2, Bool):
        return {}

    raise UnificationError(f"Cannot unify {t1} ({type(t1)}) and {t2} ({type(t2)})")


def bind(var: TVar, t: Type) -> Substitution:
    """Bind a type variable to a type (with occurs check)."""
    if var == t:
        return {}

    if var in free_type_vars(t):
        raise UnificationError(f"Occurs check failed: {var} occurs in {t}")

    if isinstance(t, RefinedType) and var == t.base_type:
        return {var: t}

    if isinstance(t, RefinedType):
        return {var: t}

    if isinstance(t, TFun):
        return {var: t}

    if isinstance(t, (Int, Bool, TVar)):
        return {var: t}

    return {var: t}


def generalize(env: TypeEnv, t: Type) -> TScheme:
    """Generalize a type into a type scheme by quantifying free vars not in env."""
    env_free_vars = set()
    for scheme in env.values():
        env_free_vars.update(free_type_vars_scheme(scheme))
    t_free_vars = free_type_vars(t)
    bound_vars = t_free_vars.difference(env_free_vars)
    return TScheme(bound_vars, t)


def instantiate(scheme: TScheme) -> Type:
    """Instantiate a type scheme by replacing bound variables with fresh ones."""
    fresh_vars_map = {old_var: generate_fresh_tvar() for old_var in scheme.bound_vars}
    return apply_sub(fresh_vars_map, scheme.monotype)


def get_base_tvar(t: Type) -> Type:
    """Unwrap RefinedType layers to get the base type variable."""
    while isinstance(t, RefinedType):
        t = t.base_type
    return t