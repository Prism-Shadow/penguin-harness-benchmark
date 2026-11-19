"""Small typed JJ template interpreter used by the stateful protocol fixture.

This implements expressions, not solver-specific output substitutions. Unsupported
syntax remains a fixture error. The real-JJ integration tests remain authoritative.
"""
import json
import re


TOKEN = re.compile(r'\s*("(?:[^"\\]|\\.)*"|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|\+\+|[().,|])')


class Parser:
    def __init__(self, source):
        self.tokens = []
        position = 0
        while position < len(source):
            match = TOKEN.match(source, position)
            if not match:
                raise ValueError('unsupported template syntax: ' + source[position:])
            self.tokens.append(match[1])
            position = match.end()
        self.index = 0

    def accept(self, token):
        if self.index < len(self.tokens) and self.tokens[self.index] == token:
            self.index += 1
            return True
        return False

    def require(self, token):
        if not self.accept(token):
            raise ValueError('expected template token: ' + token)

    def take(self):
        if self.index == len(self.tokens):
            raise ValueError('incomplete template expression')
        token = self.tokens[self.index]
        self.index += 1
        return token

    def arguments(self):
        args = []
        if self.accept(')'):
            return args
        while True:
            args.append(self.expression())
            if self.accept(')'):
                return args
            self.require(',')

    def expression(self):
        if self.accept('|'):
            name = self.take()
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
                raise ValueError('invalid lambda parameter')
            self.require('|')
            return ('lambda', name, self.expression())
        left = self.term()
        while self.accept('++'):
            left = ('concat', left, self.term())
        return left

    def term(self):
        token = self.take()
        if token == '(':
            value = self.expression()
            self.require(')')
        elif token.startswith('"'):
            # JJ string literals may contain raw control characters (for
            # example \x01 field separators); only the escapes are JSON-like.
            value = ('literal', json.loads(token, strict=False))
        elif token.isdigit():
            value = ('literal', int(token))
        elif re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', token):
            value = ('call', token, self.arguments()) if self.accept('(') else ('name', token)
        else:
            raise ValueError('unsupported template token: ' + token)
        while self.accept('.'):
            method = self.take()
            self.require('(')
            value = ('method', value, method, self.arguments())
        return value


def display(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, list):
        return ' '.join(display(item) for item in value)
    if isinstance(value, dict) and value.get('_kind') == 'ref':
        return value['name'] + ('@' + value['remote'] if value.get('remote') else '')
    if isinstance(value, str):
        return value
    raise ValueError('template value is not printable: ' + type(value).__name__)


def truthy(value):
    """JJ 0.11 converts String and List conditions: empty is false."""
    if isinstance(value, (bool, str, list)):
        return bool(value)
    raise ValueError('template value is not a boolean: ' + type(value).__name__)


def evaluate(node, record, variables):
    kind = node[0]
    if kind == 'literal':
        return node[1]
    if kind == 'name':
        if node[1] in variables:
            return variables[node[1]]
        if node[1] not in record:
            raise ValueError('unsupported template keyword: ' + node[1])
        return record[node[1]]
    if kind == 'concat':
        return display(evaluate(node[1], record, variables)) + display(evaluate(node[2], record, variables))
    if kind == 'call':
        name, arguments = node[1:]
        if name == 'if' and len(arguments) in (2, 3):
            # Only the selected branch is evaluated; a missing else is empty.
            if truthy(evaluate(arguments[0], record, variables)):
                return evaluate(arguments[1], record, variables)
            return evaluate(arguments[2], record, variables) if len(arguments) == 3 else ''
        values = [evaluate(arg, record, variables) for arg in arguments]
        # JJ 0.11 exposes this Boolean as a keyword; it is not a function.
        if name in record and not values and name != 'current_working_copy':
            return record[name]
        if name == 'concat':
            return ''.join(display(value) for value in values)
        if name == 'label' and len(values) == 2:
            return values[1]
        if name == 'separate' and len(values) >= 2:
            return display(values[0]).join(text for value in values[1:] if (text := display(value)))
        raise ValueError('unsupported template function: ' + name)
    if kind == 'method':
        source = evaluate(node[1], record, variables)
        name, arguments = node[2:]
        if name == 'map' and isinstance(source, list) and len(arguments) == 1 and arguments[0][0] == 'lambda':
            _, parameter, body = arguments[0]
            return [evaluate(body, record, dict(variables, **{parameter: item})) for item in source]
        values = [evaluate(arg, record, variables) for arg in arguments]
        if isinstance(source, dict) and name in source and not values:
            return source[name]
        if name == 'join' and isinstance(source, list) and len(values) == 1:
            return display(values[0]).join(display(item) for item in source)
        if name == 'first_line' and isinstance(source, str) and not values:
            return source.split('\n', 1)[0]
        if name in ('short', 'shortest') and isinstance(source, str) and len(values) <= 1:
            if values and (type(values[0]) is not int or values[0] < 0):
                raise ValueError('invalid identifier length')
            return source[:values[0] if values else 12]
        raise ValueError('unsupported template method: ' + name)
    raise ValueError('unsupported template expression: ' + kind)


def render(expression, record):
    expression = expression.strip()
    if not expression:
        return ''
    parser = Parser(expression)
    syntax = parser.expression()
    if parser.index != len(parser.tokens):
        raise ValueError('trailing template input')
    return display(evaluate(syntax, record, {}))
