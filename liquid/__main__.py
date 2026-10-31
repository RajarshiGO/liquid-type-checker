#!/usr/bin/env python3
"""
Liquid Types - Main Entry Point

This module provides a command-line interface and demonstration of the 
Liquid Types implementation.
"""

import sys
from typing import List

from liquid import (
    Int, Bool, Var, Lambda, App, Let, BinOp, IfExpr,
    type_check_liquid
)


def run_examples():
    """Run the built-in examples."""
    print("=" * 60)
    print("LIQUID TYPES DEMONSTRATION")
    print("=" * 60)
    
    # Qualifier templates (strings with * as placeholder for variables/constants)
    # These will be instantiated with actual program variables
    qualifier_templates = [
        "ν >= *",
        "ν == *", 
        "ν <= *",
    ]
    
    print("\nQualifier templates:", ", ".join(qualifier_templates))
    print("-" * 60)
    
    # Example 1: Integer literal
    expr1 = Int(5)
    print(f"\n1. Expression: {expr1}")
    type1 = type_check_liquid(expr1, qualifier_templates)
    print(f"   Inferred Type: {type1}")
    
    # Example 2: Boolean literal
    expr2 = Bool(True)
    print(f"\n2. Expression: {expr2}")
    type2 = type_check_liquid(expr2, qualifier_templates)
    print(f"   Inferred Type: {type2}")
    
    # Example 3: Identity function
    expr3 = Lambda('x', Var('x'))
    print(f"\n3. Expression: {expr3}")
    type3 = type_check_liquid(expr3, qualifier_templates)
    print(f"   Inferred Type: {type3}")
    
    # Example 4: max(x, y)
    max_expr = Lambda('x', Lambda('y', 
        IfExpr(BinOp('>', Var('x'), Var('y')), Var('x'), Var('y'))
    ))
    print(f"\n4. Expression: {max_expr}")
    type_max = type_check_liquid(max_expr, qualifier_templates)
    print(f"   Inferred Type: {type_max}")
    
    # Example 5: let a = 10 in (a + 5)
    expr5 = Let('a', Int(10), BinOp('+', Var('a'), Int(5)))
    print(f"\n5. Expression: {expr5}")
    type5 = type_check_liquid(expr5, qualifier_templates)
    print(f"   Inferred Type: {type5}")
    
    # Example 6: let id = (\\x. x) in (id 5)
    expr6_id = Lambda('x', Var('x'))
    expr6 = Let('id', expr6_id, App(Var('id'), Int(5)))
    print(f"\n6. Expression: {expr6}")
    type6 = type_check_liquid(expr6, qualifier_templates)
    print(f"   Inferred Type: {type6}")
    
    # Example 7: let id = (\\x. x) in (id True)
    expr7 = Let('id', Lambda('x', Var('x')), App(Var('id'), Bool(True)))
    print(f"\n7. Expression: {expr7}")
    type7 = type_check_liquid(expr7, qualifier_templates)
    print(f"   Inferred Type: {type7}")
    
    # Example 8: max of three values
    max3_expr = Lambda('x', Lambda('y', Lambda('z', IfExpr(
        BinOp('>', Var('x'), Var('y')),
        IfExpr(BinOp('>', Var('x'), Var('z')), Var('x'), Var('z')),
        IfExpr(BinOp('>', Var('y'), Var('z')), Var('y'), Var('z'))
    ))))
    print(f"\n8. Expression: {max3_expr}")
    type_max3 = type_check_liquid(max3_expr, qualifier_templates)
    print(f"   Inferred Type: {type_max3}")
    
    print("\n" + "=" * 60)
    print("DEMONSTRATION COMPLETE")
    print("=" * 60)


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] in ['-h', '--help']:
            print("Liquid Types - Refinement Type Inference for Python")
            print()
            print("Usage:")
            print("  python -m liquid              Run built-in examples")
            print("  python -m liquid --help       Show this help")
            print()
            print("For programmatic use, import from liquid:")
            print("  from liquid import Int, Var, Lambda, type_check_liquid, ...")
            return
    
    run_examples()


if __name__ == "__main__":
    main()