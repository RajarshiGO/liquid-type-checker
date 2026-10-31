# Implementation of the Liquid Types system in Pythin

> **Lightweight formal verification** — automatically discover invariants like "this variable is always non-negative" or "this index is within array bounds" without writing proofs.

---

## What is this?

**Liquid Types** (Logically Qualified Types) extend regular type systems with **refinement types**. Instead of just saying "this is an `int`", you can say "this is an `{int | ν >= 0}`" — an integer that's guaranteed to be non-negative.

The magic? You don't write the predicates yourself. The system **infers them automatically** using an SMT solver (Z3).

```python
# You write:
let x = 10 in x + 5

# Liquid Types infers:
{ int | ν >= x AND ν >= 0 }   # "the result is ≥ x AND ≥ 0"
```

---

## Why should you care?

| Regular Types | Liquid Types |
|---------------|--------------|
| `int` | `{ int | 0 ≤ ν < len }` — **array index in bounds** |
| `int` | `{ int | ν > 0 }` — **strictly positive** (no division by zero!) |
| `List a` | `{ List a | len ≥ 1 }` — **non-empty list** (safe `head`) |
| `a -> b` | `{ a -> b | x > 0 ⇒ f(x) > 0 }` — **function preserves positivity** |

---

## Quick Start

```bash
pip install z3-solver
pip install -e .        # from this repo
```

```python
from liquid import Int, Var, Lambda, BinOp, IfExpr, Let, App, type_check_liquid

# Define what *kinds* of predicates to look for (templates with *)
qualifiers = ["ν >= *", "ν == *", "ν <= *"]

# Expression: max(x, y) = if x > y then x else y
max_fn = Lambda('x', Lambda('y', 
    IfExpr(BinOp('>', Var('x'), Var('y')), Var('x'), Var('y'))
))

result = type_check_liquid(max_fn, qualifiers)
print(result)
# (int -> (int -> { int | ν >= x AND ν >= y }))
#           ↑                    ↑
#           │                    └── "return value is ≥ both inputs"
#           └── function taking two ints
```

**Run the demo:**
```bash
python -m liquid
```

---

## How it works (in plain English)

### 1. Regular type inference first
We run standard Hindley-Milner (like ML/Haskell) to get base types: `int`, `bool`, `a -> b`, etc.

### 2. Add "mystery predicates" everywhere
Every type gets a placeholder `κ` (kappa): `{ int | κ₀ }`, `{ int | κ₁ }`, ...
We don't know what `κ` is yet — that's what we're solving for.

### 3. Collect constraints as we go
While type-checking, we track: *"under this path condition, this expression equals this value"*
```
(if x > y then x else y)
     │         │      └── κ₂: value = y  (when x ≤ y)
     │         └── κ₁: value = x  (when x > y)
     └── path condition: x > y
```

### 4. Guess-and-check with Z3
You give us **qualifier templates** like `ν >= *`. We instantiate `*` with every variable and constant in scope:
- `ν >= 0`
- `ν >= x`
- `ν >= y`
- `ν == 0`
- `ν == x`
- ...

Then for each `κ`, we ask Z3: *"Is this qualifier true for ALL values this expression can take?"* We keep the ones that pass, conjoin them, and repeat until nothing changes (fixed point).

### 5. You get concrete predicates
```
κ₀ = ν >= x AND ν >= y    # strongest thing true in BOTH branches
```

---

## What's in the box

```
liquid/
├── types.py         # int, bool, type vars, functions, polymorphism, refinements
├── predicates.py    # true, comparisons (>, <, >=, <=, ==, !=), AND, NOT
├── expressions.py   # variables, lambdas, apps, lets, binary ops, if-then-else
├── constraints.py   # Z3 constraint generation + fixed-point solving
├── inference.py     # Main algorithm tying it all together
└── __main__.py      # CLI demo
```

**Tests:** 40 passing (`pytest tests/`)  
**Examples:** `python examples/basic_examples.py`

---

## Real examples from the test suite

| Expression | Inferred Type |
|------------|---------------|
| `5` | `{ int | ν >= 0 }` |
| `\\x. x` | `'a -> 'a` (polymorphic, no refinement needed) |
| `\\x. \\y. if x > y then x else y` | `int -> int -> { int | ν >= x AND ν >= y }` |
| `let a = 10 in a + 5` | `{ int | ν >= a AND ν >= 0 }` |
| `let id = (\\x. x) in id 5` | `{ int | ν >= 0 }` |
| `\\x. \\y. \\z. max3(x,y,z)` | `int -> int -> int -> { int | ν >= x AND ν >= y AND ν >= z }` |

---

## Extending it

**Custom qualifiers for your domain:**
```python
# Array bounds checking
qualifiers = [
    "ν >= 0",        # non-negative index
    "ν < len",       # within array length
    "ν == *",        # exact values
]

# Or use ComparisonPred directly for more control
from liquid import ComparisonPred
custom = [
    ComparisonPred(">=", "ν", "0"),
    ComparisonPred("<", "ν", "len"),
]
```

**Add new expression types:**
1. Add AST node in `expressions.py`
2. Handle it in `ConstraintGenerator.generate()` (constraints.py)
3. Handle it in `infer()` (inference.py)

---

## Theory & References

This implements the approach from:
- **Liquid Types** — Rondon, Kawaguchi, Jhala (PLDI 2008)
- **Hindley-Milner** — Damas & Milner (1982)
- **Refinement Types** — Freeman & Pfenning (1991)

Key insight: restrict predicates to **quantifier-free linear arithmetic** + **finite qualifier templates** → decidable, automated via SMT.

---

## Current Limitations (Future Work)

- [ ] Algebraic data types (enums, records)
- [ ] Dependent function types (refinements on arguments)
- [ ] Recursive data structures with measures
- [ ] Python `typing.Annotated` integration
- [ ] Better error messages with source locations
- [ ] Abduction-based qualifier synthesis

---

## License

MIT — do whatever you want.

---

## TL;DR

```bash
git clone https://github.com/yourusername/liquid-types
cd liquid-types
pip install -e .
python -m liquid      # see it in action
pytest tests/         # verify it works
```

Then import `from liquid import ...` and start inferring invariants automatically.
