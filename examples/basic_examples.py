#!/usr/bin/env python3
"""
Basic examples demonstrating Liquid Types usage.

This file shows how to use the liquid types library programmatically
to infer refinement types for various expressions.
"""

from liquid import (
    # Types
    Int, Bool, TVar, TFun, TScheme, RefinedType,
    # Expressions
    Var, Lambda, App, Let, BinOp, IfExpr,
    # Type checking
    type_check_liquid,
    # Predicates
    TruePred, ComparisonPred, AndPred, NotPred, PredicatePlaceholder,
    # Inference internals (for advanced use)
    infer, ConstraintGenerator, ConstraintSolver,
    collect_kappas_from_type, replace_placeholders,
)


def run_basic_examples():
    """Run basic type checking examples."""
    print("=" * 70)
    print("LIQUID TYPES - BASIC EXAMPLES")
    print("=" * 70)
    
    # Qualifier templates for the solver (strings with * as placeholder)
    # These will be instantiated with actual program variables and constants
    qualifier_templates = [
        "ν >= *",   # ν >= variable or constant
        "ν == *",   # ν == variable or constant
        "ν <= *",   # ν <= variable or constant
    ]
    
    print("\nQualifier Templates:")
    for q in qualifier_templates:
        print(f"  {q}")
    print()
    
    # Example 1: Simple integer literal
    print("-" * 70)
    print("Example 1: Integer literal 5")
    expr1 = Int(5)
    ty1 = type_check_liquid(expr1, qualifier_templates)
    print(f"  Expression: {expr1}")
    print(f"  Type:       {ty1}")
    # Expected: { int | ν >= 0 AND ν == 5 AND ν <= 5 } (simplified)
    
    # Example 2: Boolean literal
    print("-" * 70)
    print("Example 2: Boolean literal True")
    expr2 = Bool(True)
    ty2 = type_check_liquid(expr2, qualifier_templates)
    print(f"  Expression: {expr2}")
    print(f"  Type:       {ty2}")
    # Expected: bool (no refinement on bool with these qualifiers)
    
    # Example 3: Identity function
    print("-" * 70)
    print("Example 3: Identity function (\\x. x)")
    expr3 = Lambda('x', Var('x'))
    ty3 = type_check_liquid(expr3, qualifier_templates)
    print(f"  Expression: {expr3}")
    print(f"  Type:       {ty3}")
    # Expected: ('a0 -> 'a0) - polymorphic, no refinement
    
    # Example 4: max(x, y) function
    print("-" * 70)
    print("Example 4: max(x, y) = if x > y then x else y")
    max_expr = Lambda('x', Lambda('y', 
        IfExpr(BinOp('>', Var('x'), Var('y')), Var('x'), Var('y'))
    ))
    ty4 = type_check_liquid(max_expr, qualifier_templates)
    print(f"  Expression: {max_expr}")
    print(f"  Type:       {ty4}")
    # Expected: (int -> (int -> { int | ν >= x AND ν >= y }))
    
    # Example 5: Let binding with arithmetic
    print("-" * 70)
    print("Example 5: let a = 10 in (a + 5)")
    expr5 = Let('a', Int(10), BinOp('+', Var('a'), Int(5)))
    ty5 = type_check_liquid(expr5, qualifier_templates)
    print(f"  Expression: {expr5}")
    print(f"  Type:       {ty5}")
    # Expected: { int | ν >= a AND ν >= 0 AND ν == 15 }
    
    # Example 6: Polymorphic identity applied to int
    print("-" * 70)
    print("Example 6: let id = (\\x. x) in (id 5)")
    expr6_id = Lambda('x', Var('x'))
    expr6 = Let('id', expr6_id, App(Var('id'), Int(5)))
    ty6 = type_check_liquid(expr6, qualifier_templates)
    print(f"  Expression: {expr6}")
    print(f"  Type:       {ty6}")
    # Expected: { int | ν >= 0 AND ν == 5 }
    
    # Example 7: Polymorphic identity applied to bool
    print("-" * 70)
    print("Example 7: let id = (\\x. x) in (id True)")
    expr7 = Let('id', Lambda('x', Var('x')), App(Var('id'), Bool(True)))
    ty7 = type_check_liquid(expr7, qualifier_templates)
    print(f"  Expression: {expr7}")
    print(f"  Type:       {ty7}")
    # Expected: bool
    
    # Example 8: Maximum of three values
    print("-" * 70)
    print("Example 8: max3(x, y, z)")
    max3_expr = Lambda('x', Lambda('y', Lambda('z', IfExpr(
        BinOp('>', Var('x'), Var('y')),
        IfExpr(BinOp('>', Var('x'), Var('z')), Var('x'), Var('z')),
        IfExpr(BinOp('>', Var('y'), Var('z')), Var('y'), Var('z'))
    ))))
    ty8 = type_check_liquid(max3_expr, qualifier_templates)
    print(f"  Expression: {max3_expr}")
    print(f"  Type:       {ty8}")
    # Expected: (int -> (int -> (int -> { int | ν >= x AND ν >= y AND ν >= z })))
    
    print("\n" + "=" * 70)
    print("ALL EXAMPLES COMPLETED")
    print("=" * 70)


def run_advanced_example():
    """Show advanced usage with custom qualifiers."""
    print("\n" + "=" * 70)
    print("ADVANCED EXAMPLE: Custom Qualifiers")
    print("=" * 70)
    
    # Custom qualifiers for a specific use case
    # e.g., verifying array index bounds: 0 <= ν < len
    custom_qualifiers = [
        "ν >= 0",
        "ν < len",
        "ν == *",
    ]
    
    # Expression: let len = 10 in let idx = 5 in idx
    # (simulating array access with known length)
    expr = Let('len', Int(10), 
        Let('idx', Int(5), 
            Var('idx')
        )
    )
    
    ty = type_check_liquid(expr, custom_qualifiers)
    print(f"Expression: {expr}")
    print(f"Type:       {ty}")
    # Should infer: { int | ν >= 0 AND ν < len AND ν == 5 }


def run_inference_steps():
    """Show the intermediate steps of inference."""
    print("\n" + "=" * 70)
    print("INTERNALS: Inference Steps")
    print("=" * 70)
    
    from liquid.types import TypeEnv
    import z3
    
    # Use string templates for qualifiers
    qualifier_templates = ["ν >= *", "ν == *"]
    
    expr = Let('x', Int(5), BinOp('+', Var('x'), Int(3)))
    
    # Step 1: Create constraint generator and infer HM types with placeholders
    TVar.next_id = 0
    env: TypeEnv = {}
    z3_vars = {}
    cg = ConstraintGenerator()
    
    sub, inferred_type = infer(env, expr, cg, z3.BoolVal(True), z3_vars)
    
    print(f"1. HM Type with placeholders: {inferred_type}")
    print(f"   Substitution: {sub}")
    print(f"   Constraints collected: {len(cg.constraints)}")
    for ctx, kappa, val in cg.constraints:
        print(f"     {kappa}: {val} under {ctx}")
    
    # Step 2: Collect all kappa variables
    from liquid import collect_kappas_from_type
    all_kappas = set()
    collect_kappas_from_type(inferred_type, all_kappas)
    for _, k, _ in cg.constraints:
        all_kappas.add(k)
    print(f"   Kappa variables: {all_kappas}")
    
    # Step 3: Solve constraints
    solver = ConstraintSolver(qualifier_templates)
    solutions = solver.solve(cg.constraints, z3_vars, all_kappas)
    print(f"   Solutions:")
    for k, pred in solutions.items():
        print(f"     {k} = {pred}")
    
    # Step 4: Apply substitution and replace placeholders
    from liquid import apply_sub, replace_placeholders
    final_type = apply_sub(sub, inferred_type)
    liquid_type = replace_placeholders(final_type, solutions)
    print(f"2. Final Liquid Type: {liquid_type}")


if __name__ == "__main__":
    run_basic_examples()
    run_advanced_example()
    run_inference_steps()