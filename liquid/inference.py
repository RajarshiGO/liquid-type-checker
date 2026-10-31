"""
Type inference for Liquid Types.

This module implements the main type inference algorithm that:
1. Infers Hindley-Milner types with refinement placeholders
2. Collects constraints during inference
3. Solves constraints to obtain concrete refinement predicates
"""

from typing import Dict, Set, Tuple, List, Optional
import z3

from liquid.types import (
    Type, Int, Bool, TVar, TFun, TScheme, RefinedType,
    Substitution, TypeEnv, UnificationError,
    apply_sub, apply_sub_to_env, compose_subs, unify, bind,
    generalize, instantiate, generate_fresh_tvar, get_base_tvar
)
from liquid.expressions import Expr, Var, Lambda, App, Let, BinOp, IfExpr
from liquid.predicates import Predicate, TruePred, ComparisonPred, PredicatePlaceholder
from liquid.constraints import ConstraintGenerator, ConstraintSolver
from liquid.types import free_type_vars


class InferenceError(Exception):
    """Raised when type inference fails."""
    pass


def infer(env: TypeEnv, expr: Expr,
          cg: ConstraintGenerator,
          path_cond_z3: z3.ExprRef,
          z3_program_vars: Dict[str, z3.ExprRef]) -> Tuple[Substitution, Type]:
    """
    Infer the type of an expression, collecting liquid type constraints.
    
    Args:
        env: Type environment mapping variable names to type schemes
        expr: Expression to type check
        cg: Constraint generator for collecting refinement constraints
        path_cond_z3: Current path condition as Z3 expression
        z3_program_vars: Mapping from program variable names to Z3 expressions
        
    Returns:
        Tuple of (substitution, inferred_type_with_refinement_placeholders)
    """
    
    if isinstance(expr, Int):
        inferred_type_with_liquid_pred, _ = cg.generate(expr, path_cond_z3, z3_program_vars)
        return {}, inferred_type_with_liquid_pred

    if isinstance(expr, Bool):
        inferred_type_with_liquid_pred, _ = cg.generate(expr, path_cond_z3, z3_program_vars)
        return {}, inferred_type_with_liquid_pred

    if isinstance(expr, Var):
        expr_id = id(expr)
        if expr_id in cg.memo:
            return {}, cg.memo[expr_id][0]
        
        if expr.name in env:
            # Variable in environment - instantiate its type scheme
            inferred_type = instantiate(env[expr.name])

            if expr.name not in z3_program_vars:
                if isinstance(inferred_type, RefinedType) and isinstance(inferred_type.base_type, Int):
                    z3_program_vars[expr.name] = z3.Int(expr.name)
                elif isinstance(inferred_type, RefinedType) and isinstance(inferred_type.base_type, Bool):
                    z3_program_vars[expr.name] = z3.Bool(expr.name)
                else:
                    z3_program_vars[expr.name] = z3.Int(expr.name)
            
            z3_val_for_var = z3_program_vars[expr.name]
            cg.memo[expr_id] = (inferred_type, z3_val_for_var)
            return {}, inferred_type
        else:
            # Free variable - create fresh type variable with placeholder predicate
            hm_base_type = generate_fresh_tvar()
            inferred_type = RefinedType(hm_base_type, TruePred())

            if expr.name not in z3_program_vars:
                z3_program_vars[expr.name] = z3.Int(expr.name)
            z3_val_for_var = z3_program_vars[expr.name]

            kappa = cg.fresh_kappa()
            inferred_type_with_placeholder = RefinedType(
                inferred_type.base_type, 
                PredicatePlaceholder(kappa)
            )
            cg.constraints.append((path_cond_z3, kappa, z3_val_for_var))

            cg.memo[expr_id] = (inferred_type_with_placeholder, z3_val_for_var)
            return {}, inferred_type_with_placeholder

    if isinstance(expr, BinOp):
        s_left_op, t_left_op = infer(env, expr.left, cg, path_cond_z3, z3_program_vars)
        env_after_left = apply_sub_to_env(s_left_op, env)
        s_right_op, t_right_op = infer(env_after_left, expr.right, cg, path_cond_z3, z3_program_vars)
        
        if not isinstance(t_left_op, RefinedType):
            t_left_op = RefinedType(t_left_op, TruePred())
        if not isinstance(t_right_op, RefinedType):
            t_right_op = RefinedType(t_right_op, TruePred())
            
        s_ops = compose_subs(s_left_op, s_right_op)

        _, left_z3_val = cg.memo[id(expr.left)]
        _, right_z3_val = cg.memo[id(expr.right)]

        inferred_type_with_liquid_pred, _ = cg.generate(expr, path_cond_z3, z3_program_vars,
                                                        op=expr.op,
                                                        left_z3_val=left_z3_val, 
                                                        right_z3_val=right_z3_val)

        # Unify operands to Int for arithmetic/comparison ops
        s_left_int = unify(apply_sub(s_ops, t_left_op.base_type), Int())
        s_ops = compose_subs(s_ops, s_left_int)
        s_right_int = unify(apply_sub(s_ops, t_right_op.base_type), Int())
        s_ops = compose_subs(s_ops, s_right_int)

        # Unify the result's base type
        if expr.op in ['>', '<', '>=', '<=', '==', '!=']:
            result_base_type_for_unify = Bool()
        else:
            result_base_type_for_unify = Int()

        s_unify_result_base = unify(
            apply_sub(s_ops, inferred_type_with_liquid_pred.base_type), 
            result_base_type_for_unify
        )
        s_ops = compose_subs(s_ops, s_unify_result_base)
        return s_ops, apply_sub(s_ops, inferred_type_with_liquid_pred)

    if isinstance(expr, IfExpr):
        s_cond, t_cond = infer(env, expr.condition, cg, path_cond_z3, z3_program_vars)
        env_after_cond = apply_sub_to_env(s_cond, env)

        # New path conditions for then/else branches
        _, cond_z3_val = cg.memo[id(expr.condition)]
        then_path_cond_z3 = z3.And(path_cond_z3, cond_z3_val)
        else_path_cond_z3 = z3.And(path_cond_z3, z3.Not(cond_z3_val))

        s_then, t_then = infer(env_after_cond, expr.then_expr, cg, then_path_cond_z3, z3_program_vars)
        env_after_then = apply_sub_to_env(s_then, env_after_cond)
        s_else, t_else = infer(env_after_then, expr.else_expr, cg, else_path_cond_z3, z3_program_vars)

        s_combined_if = compose_subs(s_cond, compose_subs(s_then, s_else))

        _, then_z3_val = cg.memo[id(expr.then_expr)]
        _, else_z3_val = cg.memo[id(expr.else_expr)]

        inferred_type_with_liquid_pred, _ = cg.generate(expr, path_cond_z3, z3_program_vars,
                                                        cond_z3_val=cond_z3_val,
                                                        then_z3_val=then_z3_val,
                                                        else_z3_val=else_z3_val)

        s_unify_then = unify(
            apply_sub(s_combined_if, t_then.base_type), 
            inferred_type_with_liquid_pred.base_type
        )
        s_combined_if = compose_subs(s_combined_if, s_unify_then)
        s_unify_else = unify(
            apply_sub(s_combined_if, t_else.base_type), 
            inferred_type_with_liquid_pred.base_type
        )
        s_combined_if = compose_subs(s_combined_if, s_unify_else)

        return s_combined_if, apply_sub(s_combined_if, inferred_type_with_liquid_pred)

    if isinstance(expr, Lambda):
        param_type_hm = generate_fresh_tvar()

        new_env_for_body = env.copy()
        if expr.param not in z3_program_vars:
            z3_program_vars[expr.param] = z3.Int(expr.param)
        new_env_for_body[expr.param] = TScheme(set(), param_type_hm)
        
        s_body, t_body = infer(new_env_for_body, expr.body, cg, path_cond_z3, z3_program_vars)
        s_combined_lambda = s_body

        final_param_type = apply_sub(s_combined_lambda, param_type_hm)
        final_return_type = apply_sub(s_combined_lambda, t_body)

        lambda_type = TFun(final_param_type, final_return_type)

        cg.memo[id(expr)] = (lambda_type, z3.Int('lambda_val_dummy'))
        return s_combined_lambda, lambda_type

    if isinstance(expr, App):
        s_func, t_func = infer(env, expr.func, cg, path_cond_z3, z3_program_vars)
        env_for_arg = apply_sub_to_env(s_func, env)
        s_arg, t_arg = infer(env_for_arg, expr.arg, cg, path_cond_z3, z3_program_vars)
        s_combined = compose_subs(s_func, s_arg)

        t_func_subst = apply_sub(s_combined, t_func)
        t_arg_subst = apply_sub(s_combined, t_arg)

        final_app_type = None

        if isinstance(t_func_subst, TFun) and isinstance(t_func_subst.return_type, RefinedType):
            def substitute_type_var(typ, var_to_replace, replacement):
                if isinstance(typ, TVar):
                    base_var_to_replace = get_base_tvar(var_to_replace)
                    base_typ = get_base_tvar(typ)
                    if isinstance(base_typ, TVar) and base_typ.name == base_var_to_replace.name:
                        return replacement
                    else:
                        return typ
                elif isinstance(typ, RefinedType):
                    new_base = substitute_type_var(typ.base_type, var_to_replace, replacement)
                    return RefinedType(new_base, typ.predicate)
                elif isinstance(typ, TFun):
                    new_param = substitute_type_var(typ.param_type, var_to_replace, replacement)
                    new_ret = substitute_type_var(typ.return_type, var_to_replace, replacement)
                    return TFun(new_param, new_ret)
                else:
                    return typ

            param_type_var = t_func_subst.param_type
            instantiated_base = substitute_type_var(
                t_func_subst.return_type.base_type, param_type_var, t_arg_subst
            )
            instantiated_pred = t_func_subst.return_type.predicate
            instantiated_ret = RefinedType(instantiated_base, instantiated_pred)
            
            s_unify = unify(param_type_var, t_arg_subst)
            s_combined = compose_subs(s_combined, s_unify)
            final_app_type = instantiated_ret
        else:
            result_base_tvar = generate_fresh_tvar()
            s_unify_app = unify(
                t_func_subst,
                TFun(t_arg_subst, RefinedType(result_base_tvar, TruePred()))
            )
            s_combined = compose_subs(s_combined, s_unify_app)
            substituted_result_base = apply_sub(s_combined, result_base_tvar)
            kappa = cg.fresh_kappa()
            final_app_type = RefinedType(substituted_result_base, PredicatePlaceholder(kappa))

        base_type = final_app_type.base_type if isinstance(final_app_type, RefinedType) else final_app_type
        if isinstance(base_type, Bool):
            result_z3_val = z3.Bool(f"app_result_val_{id(expr)}")
        elif isinstance(base_type, Int):
            result_z3_val = z3.Int(f"app_result_val_{id(expr)}")
        else:
            result_z3_val = z3.Int(f"app_result_val_{id(expr)}")

        kappa = cg.fresh_kappa()
        cg.constraints.append((path_cond_z3, kappa, result_z3_val))
        cg.memo[id(expr)] = (final_app_type, result_z3_val)

        return s_combined, final_app_type

    if isinstance(expr, Let):
        s1, t1 = infer(env, expr.expr1, cg, path_cond_z3, z3_program_vars)
        _, z3_val_bound_expr = cg.memo[id(expr.expr1)]

        if expr.var_name not in z3_program_vars:
            if isinstance(t1, RefinedType) and isinstance(t1.base_type, Int):
                z3_program_vars[expr.var_name] = z3.Int(expr.var_name)
            elif isinstance(t1, RefinedType) and isinstance(t1.base_type, Bool):
                z3_program_vars[expr.var_name] = z3.Bool(expr.var_name)
            else:
                z3_program_vars[expr.var_name] = z3.Int(expr.var_name)

        let_binding_assertion = (z3_program_vars[expr.var_name] == z3_val_bound_expr)
        new_path_cond_for_expr2 = z3.And(path_cond_z3, let_binding_assertion)
        
        general_type_scheme = generalize(apply_sub_to_env(s1, env), t1)
        new_env = apply_sub_to_env(s1, env).copy()
        new_env[expr.var_name] = general_type_scheme
        
        s2, t2 = infer(new_env, expr.expr2, cg, new_path_cond_for_expr2, z3_program_vars)
        final_s = compose_subs(s1, s2)
        return final_s, t2

    raise InferenceError(f"Unknown expression type for infer: {type(expr)}")


def collect_kappas_from_type(t: Type, kappa_set: Set[str]) -> None:
    """Collect all kappa variable names from a type (recursively)."""
    if isinstance(t, RefinedType):
        if isinstance(t.predicate, PredicatePlaceholder):
            kappa_set.add(t.predicate.kappa_name)
        collect_kappas_from_type(t.base_type, kappa_set)
    elif isinstance(t, TFun):
        collect_kappas_from_type(t.param_type, kappa_set)
        collect_kappas_from_type(t.return_type, kappa_set)
    elif isinstance(t, TScheme):
        collect_kappas_from_type(t.monotype, kappa_set)


def replace_placeholders(t: Type, kappa_solutions: Dict[str, Predicate]) -> Type:
    """Replace predicate placeholders with solved predicates."""
    from liquid.predicates import simplify_predicate, TruePred
    
    if isinstance(t, TVar):
        return RefinedType(t, TruePred())
    if isinstance(t, Int):
        return RefinedType(t, TruePred())
    if isinstance(t, Bool):
        return RefinedType(t, TruePred())

    if isinstance(t, RefinedType):
        new_base_type = replace_placeholders(t.base_type, kappa_solutions)
        actual_predicate = kappa_solutions.get(t.predicate.kappa_name, TruePred()) \
                           if isinstance(t.predicate, PredicatePlaceholder) \
                           else t.predicate
        simplified_actual_predicate = simplify_predicate(actual_predicate)
        return RefinedType(new_base_type, simplified_actual_predicate)

    elif isinstance(t, TFun):
        return TFun(
            replace_placeholders(t.param_type, kappa_solutions),
            replace_placeholders(t.return_type, kappa_solutions)
        )
    elif isinstance(t, TScheme):
        return TScheme(t.bound_vars, replace_placeholders(t.monotype, kappa_solutions))
    return t


def type_check_liquid(expr: Expr, qualifiers: List[Predicate]) -> Type:
    """
    Main entry point for liquid type checking.
    
    Args:
        expr: Expression to type check
        qualifiers: List of qualifier predicates (templates instantiated with program vars)
        
    Returns:
        Fully refined type with solved predicates
    """
    TVar.next_id = 0
    initial_env: TypeEnv = {}
    z3_program_vars: Dict[str, z3.ExprRef] = {}
    cg = ConstraintGenerator()
    
    final_sub, inferred_hm_type = infer(
        initial_env, expr, cg, z3.BoolVal(True), z3_program_vars
    )
    
    all_kappa_names = set()
    collect_kappas_from_type(inferred_hm_type, all_kappa_names)
    for _, kappa_name, _ in cg.constraints:
        all_kappa_names.add(kappa_name)
    
    solver = ConstraintSolver(qualifiers)
    kappa_solutions = solver.solve(cg.constraints, z3_program_vars, all_kappa_names)
    
    final_type_with_placeholders = apply_sub(final_sub, inferred_hm_type)
    liquid_inferred_type = replace_placeholders(final_type_with_placeholders, kappa_solutions)
    
    return liquid_inferred_type