"""
Liquid Types - Implementation of Liquid Types over Hindley-Milner Algorithm

This package implements a type system that combines Hindley-Milner type inference
with Liquid Types (refinement types), using Z3 SMT solver for constraint solving.
"""

from liquid.types import (
    Type, Int, Bool, TVar, TFun, TScheme, RefinedType,
    free_type_vars, free_type_vars_scheme, generate_fresh_tvar,
    Substitution, apply_sub, apply_sub_to_env, compose_subs,
    unify, bind, generalize, instantiate, get_base_tvar,
    TypeEnv, UnificationError
)

from liquid.predicates import (
    Predicate, TruePred, ComparisonPred, AndPred, NotPred,
    PredicatePlaceholder, simplify_predicate
)

from liquid.expressions import (
    Expr, Var, Lambda, App, Let, BinOp, IfExpr
)

from liquid.inference import (
    infer, collect_kappas_from_type, replace_placeholders,
    type_check_liquid, InferenceError
)

from liquid.constraints import ConstraintGenerator, ConstraintSolver

__all__ = [
    # Types
    "Type", "Int", "Bool", "TVar", "TFun", "TScheme", "RefinedType",
    "free_type_vars", "free_type_vars_scheme", "generate_fresh_tvar",
    "Substitution", "apply_sub", "apply_sub_to_env", "compose_subs",
    "unify", "bind", "generalize", "instantiate", "get_base_tvar",
    "TypeEnv", "UnificationError",
    # Predicates
    "Predicate", "TruePred", "ComparisonPred", "AndPred", "NotPred",
    "PredicatePlaceholder", "simplify_predicate",
    # Expressions
    "Expr", "Var", "Lambda", "App", "Let", "BinOp", "IfExpr",
    # Inference
    "infer", "collect_kappas_from_type", "replace_placeholders",
    "type_check_liquid", "InferenceError",
    # Constraints
    "ConstraintGenerator", "ConstraintSolver",
]