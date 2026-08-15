from __future__ import annotations

from sympy import Eq, Symbol, simplify, sympify
from sympy.solvers.inequalities import solve_univariate_inequality

x = Symbol("x")


def _expr(text: str):
    """Parse the small algebra subset used by the demo question bank."""
    return sympify(text.replace("^", "**"), locals={"x": x})


def validate_solution(equation: str, candidate: str) -> bool:
    """Return True when candidate satisfies an equation such as '2*x+3=7'."""
    try:
        left, right = equation.split("=", maxsplit=1)
        value = _expr(candidate)
        result = simplify(_expr(left).subs(x, value) - _expr(right).subs(x, value))
        return bool(result == 0)
    except (TypeError, ValueError, SyntaxError):
        return False


def equivalent_equations(first: str, second: str) -> bool:
    """Check whether two linear equations differ only by a non-zero factor."""
    try:
        f_left, f_right = first.split("=", maxsplit=1)
        s_left, s_right = second.split("=", maxsplit=1)
        f = simplify(_expr(f_left) - _expr(f_right))
        s = simplify(_expr(s_left) - _expr(s_right))
        ratio = simplify(f / s)
        return bool(not ratio.has(x) and ratio != 0)
    except (TypeError, ValueError, SyntaxError, ZeroDivisionError):
        return False


def as_equation(text: str) -> Eq:
    left, right = text.split("=", maxsplit=1)
    return Eq(_expr(left), _expr(right))


def validate_inequality_answer(inequality: str, candidate: str) -> bool:
    """Check whether two single-variable real inequalities have the same solution set."""
    try:
        relation = sympify(inequality.replace("^", "**"), locals={"x": x})
        expected = solve_univariate_inequality(relation, x, relational=False)
        candidate_relation = sympify(candidate.replace("^", "**"), locals={"x": x})
        actual = solve_univariate_inequality(candidate_relation, x, relational=False)
        return bool(expected == actual)
    except (TypeError, ValueError, SyntaxError, NotImplementedError):
        return False


def number_line_description(candidate: str) -> dict[str, str | float | bool]:
    """Return a compact number-line description for x<a, x<=a, x>a or x>=a."""
    relation = sympify(candidate.replace("^", "**"), locals={"x": x})
    if relation.lhs == x:
        boundary = float(relation.rhs)
        operator = relation.rel_op
    elif relation.rhs == x:
        boundary = float(relation.lhs)
        reverse = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}
        operator = reverse[relation.rel_op]
    else:
        raise ValueError("只支持 x 与常数比较的标准解集")
    return {
        "boundary": boundary,
        "closed": operator in {"<=", ">="},
        "direction": "left" if operator in {"<", "<="} else "right",
        "operator": operator,
    }
