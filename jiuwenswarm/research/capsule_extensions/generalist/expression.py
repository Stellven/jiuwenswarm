"""A small total JSON expression language using Python syntax; never eval/exec.

This is deliberately not an arbitrary Python or OS execution environment.
Only JSON values, explicit operators and fixed pure functions are available.
"""
import ast
import json
import math
import operator
import time

from ...contracts import ResearchError


def evaluate(source, data, files):
    if not isinstance(source, str) or not 0 < len(source) <= 4096:
        raise ResearchError('generalist_expression', 'Expression must be 1..4096 characters')
    try:
        tree = ast.parse(source, mode='eval')
    except (SyntaxError, ValueError, RecursionError) as error:
        raise ResearchError('generalist_expression', 'Invalid expression') from error
    if sum(1 for _ in ast.walk(tree)) > 256:
        raise ResearchError('generalist_expression', 'Expression exceeds AST limit')
    deadline = time.monotonic() + 1
    steps = 0

    def bounded(value):
        if isinstance(value, int) and value.bit_length() > 256:
            raise ValueError('integer limit')
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError('nonfinite result')
        if isinstance(value, (list, dict)) and len(value) > 10000:
            raise ValueError('collection limit')
        if len(json.dumps(value, allow_nan=False, ensure_ascii=False).encode()) > 1024 * 1024:
            raise ValueError('byte limit')
        return value

    def visit(node, depth=0):
        nonlocal steps
        steps += 1
        if steps > 1024 or depth > 32 or time.monotonic() > deadline:
            raise ValueError('evaluation limit')
        child = lambda n: visit(n, depth + 1)
        if isinstance(node, ast.Expression):
            return child(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (str, int, float, bool, type(None)):
            value = node.value
        elif isinstance(node, ast.Name) and node.id in {'data', 'files'}:
            value = data if node.id == 'data' else files
        elif isinstance(node, (ast.List, ast.Tuple)):
            value = [child(n) for n in node.elts]
        elif isinstance(node, ast.Dict) and all(k is not None for k in node.keys):
            pairs = [(child(k), child(v)) for k, v in zip(node.keys, node.values)]
            if any(type(k) is not str for k, _ in pairs) or len({k for k, _ in pairs}) != len(pairs):
                raise ValueError('object keys')
            value = dict(pairs)
        elif isinstance(node, ast.Subscript):
            subject, key = child(node.value), child(node.slice)
            if type(subject) not in (dict, list, str) or type(key) not in (str, int):
                raise ValueError('index type')
            value = subject[key]
        elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.USub, ast.UAdd, ast.Not):
            item = child(node.operand)
            if not isinstance(node.op, ast.Not) and type(item) not in (int, float):
                raise ValueError('numeric unary operand')
            value = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Not: operator.not_}[type(node.op)](item)
        elif isinstance(node, ast.BinOp) and type(node.op) in (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod):
            left, right = child(node.left), child(node.right)
            if type(left) not in (int, float) or type(right) not in (int, float):
                raise ValueError('numeric binary operands')
            value = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}[type(node.op)](left, right)
        elif isinstance(node, ast.IfExp):
            value = child(node.body if child(node.test) else node.orelse)
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE):
            value = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
                ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge}[type(node.ops[0])](child(node.left), child(node.comparators[0]))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            args = [child(n) for n in node.args]
            functions = {'len': len, 'sum': sum, 'min': min, 'max': max, 'sorted': sorted, 'abs': abs, 'round': round}
            function = functions.get(node.func.id)
            if function is None or len(args) != 1:
                raise ValueError('unavailable function')
            arg = args[0]
            if node.func.id in {'sum', 'min', 'max'} and (type(arg) is not list or len(arg) > 10000 or any(type(x) not in (int, float) for x in arg)):
                raise ValueError('numeric sequence required')
            if node.func.id == 'sorted' and (type(arg) is not list or len(arg) > 10000):
                raise ValueError('bounded list required')
            value = function(arg)
        else:
            raise ValueError('unsupported syntax')
        return bounded(value)

    try:
        return visit(tree)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError, RecursionError) as error:
        raise ResearchError('generalist_expression', 'Expression refused: ' + str(error)[:120]) from error
