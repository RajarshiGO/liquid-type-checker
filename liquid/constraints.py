"""
Constraint generation and solving for Liquid Types.

This module handles:
1. ConstraintGenerator - Generates Z3 constraints from expressions during type inference
2. ConstraintSolver - Solves constraints by finding the strongest qualifiers from a set of templates
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Set, Optional
import z3

from liquid.types import Type
from liquid.expressions import BinOp, IfExpr
from liquid.predicates import Predicate, TruePred, ComparisonPred, AndPred, PredicatePlaceholder


class ConstraintGenerator:
    """
    Generates Z3 constraints from expressions during type inference.
    
    Performs path-sensitive analysis to collect constraints on refinement predicates.
    """
    
    def __init__(self):
        self.kappa_counter = 0
        self.constraints: List[Tuple[z3.ExprRef, str, z3.ExprRef]] = []
        # Memo stores (inferred_HM_Type, Z3_expression_for_value)
        self.memo: Dict[int, Tuple[Type, z3.ExprRef]] = {}

    def fresh_kappa(self) -> str:
        """Generate a fresh kappa variable name."""
        kappa = f"κ{self.kappa_counter}"
        self.kappa_counter += 1
        return kappa

    def generate(self, expr, path_cond_z3: z3.ExprRef, z3_program_vars: Dict[str, z3.ExprRef],
                 op: str = None, left_z3_val: z3.ExprRef = None, right_z3_val: z3.ExprRef = None,
                 cond_z3_val: z3.ExprRef = None, then_z3_val: z3.ExprRef = None,
                 else_z3_val: z3.ExprRef = None) -> Tuple[Type, z3.ExprRef]:
        """
        Generate Z3 expression for the value of `expr` and associated constraints.
        
        Returns: (inferred_HM_Type_with_LT_variable, Z3_expression_for_value)
        """
        from liquid.types import Int, Bool, RefinedType, generate_fresh_tvar
        from liquid.predicates import TruePred, PredicatePlaceholder
        
        expr_id = id(expr)
        if expr_id in self.memo:
            return self.memo[expr_id]

        hm_base_type: Type
        z3_val: z3.ExprRef
        
        if isinstance(expr, Int) and expr.value is not None:
            hm_base_type = Int()
            z3_val = z3.IntVal(expr.value)
            
        elif isinstance(expr, Bool) and expr.value is not None:
            hm_base_type = Bool()
            z3_val = z3.BoolVal(expr.value)
            
        elif isinstance(expr, BinOp):
            if left_z3_val is None or right_z3_val is None or op is None:
                raise ValueError("BinOp.generate requires left_z3_val, right_z3_val, and op")

            if op in ['>', '<', '>=', '<=', '==', '!=']:
                hm_base_type = Bool()
                z3_val = self._apply_z3_op_bool(op, left_z3_val, right_z3_val)
            else:
                hm_base_type = Int()
                z3_val = self._apply_z3_op_int(op, left_z3_val, right_z3_val)

        elif isinstance(expr, IfExpr):
            if cond_z3_val is None or then_z3_val is None or else_z3_val is None:
                raise ValueError("IfExpr.generate requires cond_z3_val, then_z3_val, and else_z3_val")

            hm_base_type = generate_fresh_tvar()

            if z3.is_int(then_z3_val) or z3.is_int(else_z3_val):
                z3_val = z3.If(cond_z3_val, then_z3_val, else_z3_val)
            elif z3.is_bool(then_z3_val) or z3.is_bool(else_z3_val):
                z3_val = z3.If(cond_z3_val, then_z3_val, else_z3_val)
            else:
                raise TypeError("then and else branches have inconsistent types")
        else:
            raise ValueError(f"Unexpected expression type: {type(expr)}")

        kappa = self.fresh_kappa()
        result_type = RefinedType(hm_base_type, PredicatePlaceholder(kappa))
        
        self.constraints.append((path_cond_z3, kappa, z3_val))

        self.memo[expr_id] = (result_type, z3_val)
        return result_type, z3_val
    
    def _apply_z3_op_int(self, op: str, left_z3: z3.ExprRef, right_z3: z3.ExprRef) -> z3.ExprRef:
        """Apply an integer binary operator to Z3 expressions."""
        if op == '+': return left_z3 + right_z3
        if op == '-': return left_z3 - right_z3
        if op == '*': return left_z3 * right_z3
        if op == '/': return left_z3 / right_z3
        raise ValueError(f"Unknown integer operator: {op}")

    def _apply_z3_op_bool(self, op: str, left_z3: z3.ExprRef, right_z3: z3.ExprRef) -> z3.ExprRef:
        """Apply a boolean binary operator to Z3 expressions."""
        if op == '>': return left_z3 > right_z3
        if op == '<': return left_z3 < right_z3
        if op == '>=': return left_z3 >= right_z3
        if op == '<=': return left_z3 <= right_z3
        if op == '==': return left_z3 == right_z3
        if op == '!=': return left_z3 != right_z3
        raise ValueError(f"Unknown boolean operator: {op}")


class ConstraintSolver:
    """
    Solves liquid type constraints by finding the strongest conjunction of qualifiers
    implied by the path conditions.
    
    Uses a fixed-point algorithm:
    1. Start with all kappa = True (weakest predicate)
    2. For each kappa, find all qualifiers implied by ALL its constraints
    3. Strengthen the predicate for that kappa
    4. Repeat until fixed point reached
    """
    
    def __init__(self, qualifier_templates):
        """
        Initialize with qualifier templates.
        
        Args:
            qualifier_templates: Either a list of template strings (e.g., ["ν >= *", "ν == *"])
                                or a list of Predicate objects to use directly.
        """
        self.qualifier_templates = qualifier_templates
        self.qualifiers: List[Predicate] = []
        self.solutions: Dict[str, Predicate] = {}

    def instantiate_qualifiers(self, all_free_vars: Dict[str, z3.ExprRef]) -> List[Predicate]:
        """Instantiate qualifier templates with program variables and constants."""
        # If templates are already Predicate objects, use them directly
        if self.qualifier_templates and isinstance(self.qualifier_templates[0], Predicate):
            return list(self.qualifier_templates)
        
        qualifiers = []
        var_names = list(all_free_vars.keys())
        constants = ["0"]

        for template_str in self.qualifier_templates:
            for val in var_names + constants:
                instantiated_str = template_str.replace("*", val)
                try:
                    op = None
                    for candidate_op in [">=", "<=", "==", ">", "<"]:
                        if candidate_op in instantiated_str:
                            op = candidate_op
                            break
                    if op is None:
                        continue

                    lhs, rhs = instantiated_str.split(op)
                    lhs = lhs.strip()
                    rhs = rhs.strip()
                    qualifiers.append(ComparisonPred(op, lhs, rhs))
                except Exception:
                    continue

        return qualifiers

    def solve(self, constraints: List[Tuple[z3.ExprRef, str, z3.ExprRef]],
              all_free_vars: Dict[str, z3.ExprRef],
              kappa_names: Set[str]) -> Dict[str, Predicate]:
        """
        Solve constraints to find strongest predicates for each kappa.
        
        Args:
            constraints: List of (path_condition, kappa_name, expr_value) tuples
            all_free_vars: Mapping from variable names to Z3 expressions
            kappa_names: Set of all kappa variable names
            
        Returns:
            Dictionary mapping kappa names to their solved predicates
        """
        from liquid.predicates import simplify_predicate
        
        self.solutions = {k_name: TruePred() for k_name in kappa_names}
        self.qualifiers = self.instantiate_qualifiers(all_free_vars)
        fixed_point_reached = False
        iteration = 0
        max_iterations = 100

        while not fixed_point_reached and iteration < max_iterations:
            fixed_point_reached = True
            iteration += 1

            for k in kappa_names:
                new_pred = TruePred()

                for q_pred in self.qualifiers:
                    is_implied_by_all_constraints_for_this_kappa = True
                    
                    for context_z3, constraint_k, expr_val_z3 in constraints:
                        if constraint_k == k:
                            solver = z3.Solver()

                            # Create nu (the value variable)
                            if z3.is_bool(expr_val_z3) or \
                               (hasattr(expr_val_z3, 'sort') and str(expr_val_z3.sort()) == 'Bool'):
                                nu = z3.Bool('nu_val')
                            elif z3.is_int(expr_val_z3) or \
                                 (hasattr(expr_val_z3, 'sort') and str(expr_val_z3.sort()) == 'Int'):
                                nu = z3.Int('nu_val')
                            else:
                                if z3.is_true(expr_val_z3) or z3.is_false(expr_val_z3):
                                    nu = z3.Bool('nu')
                                elif z3.is_int_value(expr_val_z3):
                                    nu = z3.Int('nu')
                                else:
                                    nu = z3.Int('nu_val_fallback')

                            premise = z3.And(context_z3, nu == expr_val_z3)

                            try:
                                conclusion = q_pred.to_z3(nu, all_free_vars)
                                
                                # Check: premise => conclusion
                                # Equivalent to: NOT (premise AND NOT conclusion) is satisfiable
                                solver.add(premise)
                                solver.add(z3.Not(conclusion))

                                if solver.check() == z3.sat:
                                    is_implied_by_all_constraints_for_this_kappa = False
                                    break

                            except (z3.Z3Exception, TypeError):
                                is_implied_by_all_constraints_for_this_kappa = False
                                break

                    if is_implied_by_all_constraints_for_this_kappa:
                        new_pred = AndPred(new_pred, q_pred)

                new_pred = simplify_predicate(new_pred)

                if not self._predicates_equal(self.solutions[k], new_pred, all_free_vars):
                    self.solutions[k] = new_pred
                    fixed_point_reached = False

        return self.solutions

    def _predicates_equal(self, p1: Predicate, p2: Predicate, 
                          all_free_vars: Dict[str, z3.ExprRef]) -> bool:
        """Check if two predicates are logically equivalent using Z3."""
        if p1 == p2:
            return True

        solver = z3.Solver()
        temp_nu: z3.ExprRef = z3.Int('temp_nu')
        
        # Check if predicates are boolean-typed
        for p in [p1, p2]:
            if isinstance(p, ComparisonPred):
                if (p.left == 'ν' and isinstance(p.right, str) and p.right.lower() in ['true', 'false']) or \
                   (p.right == 'ν' and isinstance(p.left, str) and p.left.lower() in ['true', 'false']):
                    temp_nu = z3.Bool('temp_nu')

        try:
            p1_z3 = p1.to_z3(temp_nu, all_free_vars)
            p2_z3 = p2.to_z3(temp_nu, all_free_vars)
        except (z3.Z3Exception, TypeError):
            return False

        solver.add(z3.Or(z3.And(p1_z3, z3.Not(p2_z3)), z3.And(p2_z3, z3.Not(p1_z3))))

        return solver.check() == z3.unsat