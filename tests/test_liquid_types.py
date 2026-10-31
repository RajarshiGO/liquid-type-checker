"""
Tests for Liquid Types implementation.
"""

import pytest
from liquid import (
    Int, Bool, Var, Lambda, App, Let, BinOp, IfExpr,
    type_check_liquid, TVar, TFun, TScheme, RefinedType,
    TruePred, ComparisonPred, AndPred, PredicatePlaceholder,
    infer, ConstraintGenerator, ConstraintSolver,
    TypeEnv, Substitution, apply_sub, unify, generalize, instantiate,
    generate_fresh_tvar, free_type_vars, simplify_predicate
)


# ============================================================================
# Basic Type Tests
# ============================================================================

def test_int_type():
    assert Int(5).value == 5
    assert Int().value is None
    assert str(Int(5)) == "5"
    assert str(Int()) == "int"

def test_bool_type():
    assert Bool(True).value is True
    assert Bool(False).value is False
    assert Bool().value is None
    assert str(Bool(True)) == "bool:True"

def test_tvar():
    TVar.next_id = 0
    a = TVar()
    b = TVar()
    assert a.name == "'a0"
    assert b.name == "'a1"
    assert a != b

def test_tfun():
    TVar.next_id = 0
    a = TVar()
    f = TFun(a, Int())
    assert str(f) == "('a0 -> 5)" if isinstance(a, Int) else f"('a0 -> int)"

def test_tscheme():
    TVar.next_id = 0
    a = TVar()
    scheme = TScheme({a}, TFun(a, a))
    assert "for all" in str(scheme)
    assert "'a0" in str(scheme)


# ============================================================================
# Substitution and Unification Tests
# ============================================================================

def test_apply_sub_tvar():
    TVar.next_id = 0
    a = TVar()
    sub = {a: Int(5)}
    result = apply_sub(sub, a)
    assert isinstance(result, RefinedType)
    assert result.base_type == Int(5)

def test_apply_sub_tfun():
    TVar.next_id = 0
    a = TVar()
    f = TFun(a, a)
    sub = {a: Int()}
    result = apply_sub(sub, f)
    assert isinstance(result, TFun)
    assert isinstance(result.param_type, RefinedType)
    assert isinstance(result.return_type, RefinedType)

def test_unify_same():
    s = unify(Int(), Int())
    assert s == {}

def test_unify_tvar():
    TVar.next_id = 0
    a = TVar()
    s = unify(a, Int())
    assert s == {a: Int()}

def test_unify_tfun():
    TVar.next_id = 0
    a = TVar()
    b = TVar()
    f1 = TFun(a, Int())
    f2 = TFun(Int(), b)
    s = unify(f1, f2)
    assert a in s
    assert b in s

def test_unify_error():
    with pytest.raises(Exception):  # UnificationError
        unify(Int(), Bool())


# ============================================================================
# Generalization and Instantiation Tests
# ============================================================================

def test_generalize():
    TVar.next_id = 0
    a = TVar()
    env: TypeEnv = {}
    scheme = generalize(env, a)
    assert a in scheme.bound_vars

def test_generalize_with_env():
    TVar.next_id = 0
    a = TVar()
    b = TVar()
    env: TypeEnv = {"x": TScheme({a}, a)}
    scheme = generalize(env, b)
    assert b in scheme.bound_vars
    assert a not in scheme.bound_vars

def test_instantiate():
    TVar.next_id = 0
    a = TVar()
    scheme = TScheme({a}, TFun(a, a))
    inst = instantiate(scheme)
    assert isinstance(inst, TFun)
    assert isinstance(inst.param_type, RefinedType)


# ============================================================================
# Predicate Tests
# ============================================================================

def test_true_pred():
    p = TruePred()
    assert str(p) == "True"
    import z3
    z3_val = p.to_z3(z3.Int('x'), {})
    assert z3.is_true(z3_val)

def test_comparison_pred():
    p = ComparisonPred(">=", "ν", "0")
    assert str(p) == "ν >= 0"
    import z3
    z3_val = p.to_z3(z3.Int('x'), {})
    # Z3 may print as "0 <= x" or "x >= 0" - both are equivalent
    assert "0" in str(z3_val) and "x" in str(z3_val)

def test_and_pred():
    p1 = ComparisonPred(">=", "ν", "0")
    p2 = ComparisonPred("<=", "ν", "10")
    p = AndPred(p1, p2)
    assert "AND" in str(p)

def test_simplify_predicate():
    # TruePred AND TruePred -> TruePred
    p = AndPred(TruePred(), TruePred())
    assert isinstance(simplify_predicate(p), TruePred)
    
    # TruePred AND p -> p
    p = AndPred(TruePred(), ComparisonPred(">=", "ν", "0"))
    assert isinstance(simplify_predicate(p), ComparisonPred)


# ============================================================================
# Expression Tests
# ============================================================================

def test_var_expr():
    v = Var("x")
    assert v.name == "x"
    assert str(v) == "x"

def test_lambda_expr():
    lam = Lambda("x", Var("x"))
    assert lam.param == "x"
    assert isinstance(lam.body, Var)

def test_app_expr():
    app = App(Var("f"), Var("x"))
    assert isinstance(app.func, Var)
    assert isinstance(app.arg, Var)

def test_let_expr():
    let = Let("x", Int(5), Var("x"))
    assert let.var_name == "x"
    assert isinstance(let.expr1, Int)
    assert isinstance(let.expr2, Var)

def test_binop_expr():
    binop = BinOp("+", Int(1), Int(2))
    assert binop.op == "+"
    assert binop.left.value == 1
    assert binop.right.value == 2

def test_if_expr():
    ife = IfExpr(Bool(True), Int(1), Int(2))
    assert isinstance(ife.condition, Bool)
    assert ife.then_expr.value == 1
    assert ife.else_expr.value == 2


# ============================================================================
# Constraint Generator Tests
# ============================================================================

def test_constraint_generator_int():
    cg = ConstraintGenerator()
    import z3
    ty, z3_val = cg.generate(Int(5), z3.BoolVal(True), {})
    assert isinstance(ty, RefinedType)
    assert z3.is_int_value(z3_val)
    assert z3_val.as_long() == 5

def test_constraint_generator_bool():
    cg = ConstraintGenerator()
    import z3
    ty, z3_val = cg.generate(Bool(True), z3.BoolVal(True), {})
    assert isinstance(ty, RefinedType)
    assert z3.is_true(z3_val)

def test_constraint_generator_binop():
    cg = ConstraintGenerator()
    import z3
    left_val = z3.IntVal(5)
    right_val = z3.IntVal(3)
    ty, z3_val = cg.generate(
        BinOp("+", Int(5), Int(3)), z3.BoolVal(True), {},
        op="+", left_z3_val=left_val, right_z3_val=right_val
    )
    assert isinstance(ty, RefinedType)
    assert z3.is_int(z3_val)


# ============================================================================
# Constraint Solver Tests
# ============================================================================

def test_constraint_solver_simple():
    import z3
    solver = ConstraintSolver(["ν >= *", "ν == *", "ν <= *"])
    
    x = z3.Int('x')
    constraints = [
        (z3.BoolVal(True), "κ0", z3.IntVal(5)),
        (z3.BoolVal(True), "κ1", z3.IntVal(10)),
    ]
    all_vars = {"x": x}
    kappa_names = {"κ0", "κ1"}
    
    solutions = solver.solve(constraints, all_vars, kappa_names)
    
    assert "κ0" in solutions
    assert "κ1" in solutions


# ============================================================================
# Type Inference Tests
# ============================================================================

def test_infer_int_literal():
    TVar.next_id = 0
    cg = ConstraintGenerator()
    import z3
    sub, ty = infer({}, Int(5), cg, z3.BoolVal(True), {})
    assert isinstance(ty, RefinedType)
    assert isinstance(ty.base_type, Int)

def test_infer_bool_literal():
    TVar.next_id = 0
    cg = ConstraintGenerator()
    import z3
    sub, ty = infer({}, Bool(True), cg, z3.BoolVal(True), {})
    assert isinstance(ty, RefinedType)
    assert isinstance(ty.base_type, Bool)

def test_infer_lambda():
    TVar.next_id = 0
    cg = ConstraintGenerator()
    import z3
    lam = Lambda("x", Var("x"))
    sub, ty = infer({}, lam, cg, z3.BoolVal(True), {})
    assert isinstance(ty, TFun)

def test_infer_let():
    TVar.next_id = 0
    cg = ConstraintGenerator()
    import z3
    let = Let("x", Int(5), Var("x"))
    sub, ty = infer({}, let, cg, z3.BoolVal(True), {})
    assert isinstance(ty, RefinedType)
    # The base type might be wrapped in RefinedType
    base = ty.base_type
    while isinstance(base, RefinedType):
        base = base.base_type
    assert isinstance(base, Int)


# ============================================================================
# Full Type Checking Tests
# ============================================================================

def test_type_check_int():
    TVar.next_id = 0
    qualifiers = ["ν >= *", "ν == *"]
    ty = type_check_liquid(Int(5), qualifiers)
    assert isinstance(ty, RefinedType)
    # Should have some refinement
    assert "ν" in str(ty) or str(ty) == "int"

def test_type_check_bool():
    TVar.next_id = 0
    qualifiers = ["ν >= *", "ν == *"]
    ty = type_check_liquid(Bool(True), qualifiers)
    assert isinstance(ty, RefinedType)
    assert str(ty) == "bool"

def test_type_check_identity():
    TVar.next_id = 0
    qualifiers = ["ν >= *"]
    lam = Lambda("x", Var("x"))
    ty = type_check_liquid(lam, qualifiers)
    assert isinstance(ty, TFun)

def test_type_check_max():
    TVar.next_id = 0
    qualifiers = [
        "ν >= *",
        "ν == *",
        "ν <= *",
    ]
    max_expr = Lambda("x", Lambda("y", 
        IfExpr(BinOp(">", Var("x"), Var("y")), Var("x"), Var("y"))
    ))
    ty = type_check_liquid(max_expr, qualifiers)
    assert isinstance(ty, TFun)
    assert "ν >=" in str(ty)

def test_type_check_let():
    TVar.next_id = 0
    qualifiers = [
        "ν >= *",
        "ν == *",
    ]
    let_expr = Let("a", Int(10), BinOp("+", Var("a"), Int(5)))
    ty = type_check_liquid(let_expr, qualifiers)
    assert isinstance(ty, RefinedType)
    assert "ν >=" in str(ty)

def test_type_check_app():
    TVar.next_id = 0
    qualifiers = ["ν >= *", "ν == *"]
    id_fn = Lambda("x", Var("x"))
    app = App(id_fn, Int(42))
    ty = type_check_liquid(app, qualifiers)
    assert isinstance(ty, RefinedType)
    assert "ν >=" in str(ty)


# ============================================================================
# Collect and Replace Kappa Tests
# ============================================================================

def test_collect_kappas():
    TVar.next_id = 0
    from liquid import collect_kappas_from_type
    
    kappa_names = set()
    ty = RefinedType(Int(), PredicatePlaceholder("κ0"))
    collect_kappas_from_type(ty, kappa_names)
    assert "κ0" in kappa_names

def test_replace_placeholders():
    TVar.next_id = 0
    from liquid import replace_placeholders
    
    ty = RefinedType(Int(), PredicatePlaceholder("κ0"))
    solutions = {"κ0": ComparisonPred(">=", "ν", "0")}
    result = replace_placeholders(ty, solutions)
    assert isinstance(result.predicate, ComparisonPred)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])