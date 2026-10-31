"""
Predicate classes for Liquid Types.

Predicates represent logical constraints on refined types.
They can be converted to Z3 expressions for SMT solving.
"""

from dataclasses import dataclass
from typing import Dict
import z3


class Predicate:
    """Base class for refinement predicates."""
    
    def to_z3(self, val: z3.ExprRef, vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
        """Convert predicate to Z3 expression."""
        raise NotImplementedError

    def __str__(self):
        return repr(self)


@dataclass(frozen=True)
class TruePred(Predicate):
    """Predicate that is always true (weakest predicate)."""
    
    def to_z3(self, val: z3.ExprRef, vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
        return z3.BoolVal(True)

    def __str__(self):
        return "True"


@dataclass(frozen=True)
class ComparisonPred(Predicate):
    """Comparison predicate: left op right."""
    op: str
    left: str
    right: str
    
    def to_z3(self, val: z3.ExprRef, vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
        """Convert comparison to Z3 expression."""
        # Handle left side
        l_expr = val if self.left == 'ν' else vars.get(self.left, z3.Int(self.left))
        
        # Handle right side
        if isinstance(self.right, str) and self.right.lower() == 'true':
            r_expr = z3.BoolVal(True)
        elif isinstance(self.right, str) and self.right.lower() == 'false':
            r_expr = z3.BoolVal(False)
        else:
            try:
                r_expr = z3.IntVal(int(self.right))
            except (ValueError, TypeError):
                r_expr = val if self.right == 'ν' else vars.get(self.right, z3.Int(self.right))

        # Check type compatibility
        l_is_int = z3.is_int(l_expr) or z3.is_int_value(l_expr)
        l_is_bool = z3.is_bool(l_expr) or z3.is_true(l_expr) or z3.is_false(l_expr)
        r_is_int = z3.is_int(r_expr) or z3.is_int_value(r_expr)
        r_is_bool = z3.is_bool(r_expr) or z3.is_true(r_expr) or z3.is_false(r_expr)
        
        if (l_is_int and r_is_bool) or (l_is_bool and r_is_int):
            if self.op in ['>', '<', '>=', '<=']:
                return z3.BoolVal(False)
            elif self.op in ['==', '!=']:
                return z3.BoolVal(False)

        # Apply operator
        op_map = {
            '>=': l_expr >= r_expr, '>': l_expr > r_expr,
            '<=': l_expr <= r_expr, '<': l_expr < r_expr,
            '==': l_expr == r_expr, '!=': l_expr != r_expr,
        }
        return op_map.get(self.op, z3.BoolVal(True))

    def __str__(self):
        return f"{self.left} {self.op} {self.right}"


@dataclass(frozen=True)
class AndPred(Predicate):
    """Conjunction of two predicates."""
    left: Predicate
    right: Predicate

    def to_z3(self, val: z3.ExprRef, vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
        return z3.And(self.left.to_z3(val, vars), self.right.to_z3(val, vars))

    def __str__(self):
        left_str = str(self.left)
        right_str = str(self.right)
        if isinstance(self.left, (AndPred, NotPred)) and not isinstance(self.left, TruePred):
            left_str = f"({left_str})"
        if isinstance(self.right, (AndPred, NotPred)) and not isinstance(self.right, TruePred):
            right_str = f"({right_str})"
        return f"{left_str} AND {right_str}"


@dataclass(frozen=True)
class NotPred(Predicate):
    """Negation of a predicate."""
    pred: Predicate

    def to_z3(self, val: z3.ExprRef, vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
        return z3.Not(self.pred.to_z3(val, vars))

    def __str__(self):
        pred_str = str(self.pred)
        if isinstance(self.pred, (AndPred, ComparisonPred)):
            pred_str = f"({pred_str})"
        return f"NOT {pred_str}"


@dataclass(frozen=True)
class PredicatePlaceholder(Predicate):
    """Placeholder for unknown predicate (kappa variable) during inference."""
    kappa_name: str

    def to_z3(self, val: z3.ExprRef, vars: Dict[str, z3.ExprRef]) -> z3.ExprRef:
        # An unknown predicate is by default assigned the weakest predicate True.
        return z3.BoolVal(True)

    def __str__(self):
        return f"κ({self.kappa_name})"


def simplify_predicate(pred: Predicate) -> Predicate:
    """Simplify predicate by removing redundant TruePred conjuncts."""
    if isinstance(pred, AndPred):
        simplified_left = simplify_predicate(pred.left)
        simplified_right = simplify_predicate(pred.right)
        
        if isinstance(simplified_left, TruePred) and isinstance(simplified_right, TruePred):
            return TruePred()
        if isinstance(simplified_left, TruePred):
            return simplified_right
        if isinstance(simplified_right, TruePred):
            return simplified_left
        if simplified_left == pred.left and simplified_right == pred.right:
            return pred
        else:
            return AndPred(simplified_left, simplified_right)
    elif isinstance(pred, NotPred):
        simplified_inner = simplify_predicate(pred.pred)
        if simplified_inner == pred.pred:
            return pred
        else:
            return NotPred(simplified_inner)
    return pred