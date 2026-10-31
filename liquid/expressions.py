"""
Expression classes for the Liquid Types language.

These represent the AST nodes for the core language:
variables, lambda abstractions, applications, let bindings,
binary operations, and if-then-else expressions.
"""

from dataclasses import dataclass


class Expr:
    """Base class for all expressions."""
    pass


class Var(Expr):
    """Variable reference."""
    
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return self.name


class Lambda(Expr):
    """Lambda abstraction: \\param. body"""
    
    def __init__(self, param: str, body: Expr):
        self.param = param
        self.body = body

    def __repr__(self):
        return f"(\\{self.param}. {self.body})"


class App(Expr):
    """Function application: (func arg)"""
    
    def __init__(self, func: Expr, arg: Expr):
        self.func = func
        self.arg = arg

    def __repr__(self):
        return f"({self.func} {self.arg})"


class Let(Expr):
    """Let binding: let var = expr1 in expr2"""
    
    def __init__(self, var_name: str, expr1: Expr, expr2: Expr):
        self.var_name = var_name
        self.expr1 = expr1
        self.expr2 = expr2

    def __repr__(self):
        return f"(let {self.var_name} = {self.expr1} in {self.expr2})"


@dataclass(frozen=True)
class BinOp(Expr):
    """Binary operation: (left op right)"""
    op: str
    left: Expr
    right: Expr

    def __repr__(self):
        return f"({self.left} {self.op} {self.right})"


@dataclass(frozen=True)
class IfExpr(Expr):
    """If-then-else expression: if condition then then_expr else else_expr"""
    condition: Expr
    then_expr: Expr
    else_expr: Expr

    def __repr__(self):
        return f"(if {self.condition} then {self.then_expr} else {self.else_expr})"