"""Test-only, neutral syntax observations for GitHub Expressions rooted in steps.

This is a bounded structural reader, not an evaluator. Calls and operators preserve
syntactic dependencies as opaque; a projection on their result is never promoted
into a direct root selector. No workflow or credential authorization lives here.
"""
from dataclasses import dataclass, replace
from functools import lru_cache
import json
import re
import unittest


@dataclass(frozen=True)
class Selector:
    kind: str
    literal_value: str | None
    text: str
    span: tuple[int, int]


@dataclass(frozen=True)
class ContextAccess:
    root: str
    selectors: tuple[Selector, ...]
    projections: tuple[tuple[Selector, ...], ...]
    span: tuple[int, int]
    opaque: bool = False


@dataclass(frozen=True)
class SyntaxIssue:
    message: str
    span: tuple[int, int]


@dataclass(frozen=True)
class ScanResult:
    accesses: tuple[ContextAccess, ...]
    issues: tuple[SyntaxIssue, ...]


@dataclass(frozen=True)
class _Token:
    kind: str
    value: str
    start: int
    end: int


@dataclass(frozen=True)
class _Node:
    kind: str
    span: tuple[int, int]
    value: str = ""
    children: tuple["_Node", ...] = ()
    selector: Selector | None = None


@dataclass(frozen=True)
class _AccessState:
    access: ContextAccess
    new_projection: bool = False
    receiver: bool = True


_WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9-]*")
_NUMBER = re.compile(r"-?(?:0[xX][0-9a-fA-F]+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)")
_OPERATORS = {"||", "&&", "==", "!=", "<=", ">=", "<", ">", "!"}


def _quoted_end(text, start, end):
    quote, cursor = text[start], start + 1
    while cursor < end:
        if text[cursor] == quote:
            if quote == "'" and cursor + 1 < end and text[cursor + 1] == quote:
                cursor += 2
                continue
            return cursor + 1
        if quote == '"' and text[cursor] == "\\":
            cursor += 1
        cursor += 1
    return None


def _regions(text, template, issues):
    if not template and not text.lstrip().startswith("${{"):
        return ((0, len(text)),)
    regions, cursor = [], 0
    while (start := text.find("${{", cursor)) >= 0:
        cursor = start + 3
        content = cursor
        while cursor < len(text):
            if text[cursor] in "'\"":
                quoted = _quoted_end(text, cursor, len(text))
                if quoted is None:
                    break
                cursor = quoted
            elif text.startswith("}}", cursor):
                regions.append((content, cursor))
                cursor += 2
                break
            else:
                cursor += 1
        else:
            cursor = len(text)
        if not regions or regions[-1][0] != content:
            issues.append(SyntaxIssue("unterminated expression template", (start, len(text))))
            regions.append((content, len(text)))
            break
    return tuple(regions)


def _lex(text, start, end, issues):
    tokens, cursor = [], start
    while cursor < end:
        if text[cursor].isspace():
            cursor += 1
            continue
        before, char = cursor, text[cursor]
        if char in "'\"":
            cursor = _quoted_end(text, before, end)
            if cursor is None:
                issues.append(SyntaxIssue("unterminated string", (before, end)))
                break
            raw = text[before:cursor]
            try:
                value = raw[1:-1].replace("''", "'") if char == "'" else json.loads(raw)
            except ValueError:
                issues.append(SyntaxIssue("unsupported quoted string", (before, cursor)))
                tokens.append(_Token("unknown", raw, before, cursor))
            else:
                tokens.append(_Token("string", value, before, cursor))
            continue
        match = _WORD.match(text, cursor) or _NUMBER.match(text, cursor)
        if match:
            cursor = match.end()
            kind = "identifier" if _WORD.fullmatch(match[0]) else "number"
            tokens.append(_Token(kind, match[0], before, cursor))
            continue
        operator = text[cursor:cursor + 2]
        if operator in _OPERATORS:
            cursor += 2
            tokens.append(_Token("operator", operator, before, cursor))
        elif char in _OPERATORS or char in ".[](),*":
            cursor += 1
            tokens.append(_Token("operator" if char in _OPERATORS else char, char, before, cursor))
        else:
            cursor += 1
            issues.append(SyntaxIssue("unsupported expression character", (before, cursor)))
            tokens.append(_Token("unknown", char, before, cursor))
    tokens.append(_Token("end", "", end, end))
    return tuple(tokens)


class _Reader:
    def __init__(self, text, tokens, issues):
        self.text, self.tokens, self.issues, self.cursor = text, tokens, issues, 0

    @property
    def current(self):
        return self.tokens[self.cursor]

    def take(self):
        current = self.current
        if current.kind != "end":
            self.cursor += 1
        return current

    def issue(self, message):
        self.issues.append(SyntaxIssue(message, (self.current.start, self.current.end)))

    def expression(self, stops=frozenset()):
        parts = [self.postfix()]
        while self.current.kind not in stops | {"end"}:
            operator = self.take()
            if operator.kind != "operator":
                self.issues.append(SyntaxIssue("unsupported expression boundary", (operator.start, operator.end)))
            parts.append(self.postfix())
        if len(parts) == 1:
            return parts[0]
        # Precedence is deliberately not evaluated: postfix ownership and explicit
        # grouping suffice; every operator result is syntactically opaque.
        return _Node("operator", (parts[0].span[0], parts[-1].span[1]), children=tuple(parts))

    def primary(self):
        current = self.take()
        if current.kind == "operator" and current.value == "!":
            child = self.postfix()
            return _Node("unary", (current.start, child.span[1]), children=(child,))
        if current.kind == "(":
            child = self.expression(frozenset({")"}))
            if self.current.kind != ")":
                self.issue("unclosed group")
                return _Node("opaque", (current.start, child.span[1]), children=(child,))
            close = self.take()
            return _Node("group", (current.start, close.end), children=(child,))
        if current.kind not in {"identifier", "string", "number"}:
            self.issues.append(SyntaxIssue("unsupported expression operand", (current.start, current.end)))
        return _Node(current.kind, (current.start, current.end), current.value)

    def postfix(self):
        base = self.primary()
        while self.current.kind in {".", "[", "("}:
            opening = self.take()
            if opening.kind == ".":
                field = self.take()
                literal = field.value if field.kind == "identifier" else None
                if field.kind not in {"identifier", "*"}:
                    self.issues.append(SyntaxIssue("missing literal property", (field.start, field.end)))
                selector = Selector("literal" if literal is not None else "dynamic", literal,
                                    self.text[opening.start:field.end], (opening.start, field.end))
                base = _Node("select", (base.span[0], field.end), children=(base,), selector=selector)
            elif opening.kind == "[":
                child = self.expression(frozenset({"]"}))
                close = self.take() if self.current.kind == "]" else self.current
                if close.kind != "]":
                    self.issue("unclosed index")
                literal_node = child
                while literal_node.kind == "group":
                    literal_node = literal_node.children[0]
                literal = literal_node.value if literal_node.kind == "string" else None
                selector = Selector("literal" if literal is not None else "dynamic", literal,
                                    self.text[opening.start:close.end], (opening.start, close.end))
                base = _Node("select", (base.span[0], close.end), children=(base, child), selector=selector)
            else:
                arguments = [base]
                while self.current.kind not in {")", "end"}:
                    arguments.append(self.expression(frozenset({",", ")"})))
                    if self.current.kind != ",":
                        break
                    self.take()
                close = self.take() if self.current.kind == ")" else self.current
                if close.kind != ")":
                    self.issue("unclosed call")
                base = _Node("call", (base.span[0], close.end), children=tuple(arguments))
        return base


def _observe(node, roots):
    if node.kind == "identifier" and node.value.casefold() in roots:
        return (_AccessState(ContextAccess(node.value.casefold(), (), (), node.span)),)
    children = tuple(_observe(child, roots) for child in node.children)
    if node.kind == "group":
        return children[0]
    if node.kind == "select":
        states = []
        for state in children[0]:
            if not state.receiver:
                states.append(state)
                continue
            access = state.access
            if access.opaque:
                projections = access.projections
                if state.new_projection or not projections:
                    projections += ((node.selector,),)
                else:
                    projections = projections[:-1] + (projections[-1] + (node.selector,),)
                access = replace(access, projections=projections)
            else:
                access = replace(access, selectors=access.selectors + (node.selector,))
            states.append(_AccessState(replace(access, span=(access.span[0], node.span[1]))))
        # An index expression has its own chains, never the receiver's continuation.
        return tuple(states) + tuple(replace(state, receiver=False) for group in children[1:] for state in group)
    return tuple(_AccessState(replace(state.access, opaque=True), True) if state.receiver else state
                 for group in children for state in group)


@lru_cache(maxsize=1024)
def scan_paths(text: str, *, roots: tuple[str, ...], template: bool = False) -> ScanResult:
    """Describe caller-selected context syntax, or only interpolations when template=True.

    Literal strings are not references. Delimiters, calls and operators never
    authorize a path. Results and every nested component are immutable.
    """
    issues, accesses = [], []
    contexts = frozenset(root.casefold() for root in roots)
    for start, end in _regions(text, template, issues):
        tokens = _lex(text, start, end, issues)
        reader = _Reader(text, tokens, issues)
        try:
            tree = reader.expression()
            accesses.extend(state.access for state in _observe(tree, contexts))
        except RecursionError:
            issues.append(SyntaxIssue("expression nesting exceeds reader capacity", (start, end)))
    return ScanResult(tuple(sorted(accesses, key=lambda access: access.span[0])), tuple(issues))


def scan_steps(text: str, *, template: bool = False) -> ScanResult:
    """Convenience syntax view of the steps context; no authorization implied."""
    return scan_paths(text, roots=("steps",), template=template)


class SyntaxContractTests(unittest.TestCase):
    """Generic syntax contract, collected through the credential policy test module.

    Fixture names are deliberately neutral; these assertions grant no authority.
    """
    extra_position_cases = ()

    def test_literal_and_dynamic_positions(self):
        cases = [("steps.alpha.items.beta", ("alpha", "items", "beta")),
                 ("steps['alpha'][\"items\"]['it''s']", ("alpha", "items", "it's")),
                 ("steps[inputs.name].items.beta", (None, "items", "beta")),
                 ("steps[(('alpha'))].items.beta", ("alpha", "items", "beta")),
                 ("steps.alpha[format('{0}]', fn(inputs.x, 'it''s'))].beta", ("alpha", None, "beta"))]
        for text, expected in (*cases, *self.extra_position_cases):
            with self.subTest(expression=text):
                result = scan_steps(text)
                self.assertFalse(result.issues)
                self.assertEqual(len(result.accesses), 1)
                actual = result.accesses[0]
                self.assertEqual(tuple(s.literal_value for s in actual.selectors), expected)
                self.assertEqual(tuple(s.kind for s in actual.selectors), tuple("dynamic" if v is None else "literal" for v in expected))
                for selector in actual.selectors:
                    self.assertEqual(text[slice(*selector.span)], selector.text)

    def test_operator_chain_and_index_ownership(self):
        cases = [("steps[inputs.name].items.alpha || steps.fallback.items.beta", ((None, "items", "alpha"), ("fallback", "items", "beta"))),
                 ("steps[steps.alpha.items.beta].items.gamma", ((None, "items", "gamma"), ("alpha", "items", "beta")))]
        for text, expected in cases:
            with self.subTest(expression=text):
                result = scan_steps(text)
                self.assertFalse(result.issues)
                self.assertEqual(tuple(tuple(s.literal_value for s in a.selectors) for a in result.accesses), expected)
                self.assertTrue(all(not a.projections for a in result.accesses))

    def test_opaque_projection_is_not_direct(self):
        result = scan_steps("fromJSON(toJSON(steps) || '{}').alpha.items.beta")
        self.assertFalse(result.issues)
        self.assertEqual(len(result.accesses), 1)
        access = result.accesses[0]
        self.assertEqual(access.selectors, ())
        self.assertTrue(access.opaque)
        self.assertEqual(tuple(tuple(s.literal_value for s in p) for p in access.projections), (("alpha", "items", "beta"),))
        envelope = scan_steps("fromJSON(format('[{0}]', toJSON(steps)))[0].alpha.items.beta").accesses[0]
        self.assertTrue(envelope.opaque)
        self.assertEqual(envelope.selectors, ())
        self.assertEqual(tuple(s.literal_value for s in envelope.projections[0]), (None, "alpha", "items", "beta"))

    def test_strings_templates_and_context_fields_are_not_roots(self):
        for text, template in [("format('steps.alpha.items.beta', env.value)", False),
                               ("env.steps.alpha.items.beta", False), ("steps.alpha.items.beta", True)]:
            with self.subTest(expression=text, template=template):
                self.assertEqual(scan_steps(text, template=template).accesses, ())
        result = scan_steps("echo '${{ steps.alpha.items.beta }}' ${{ steps.other.items.gamma }}", template=True)
        self.assertFalse(result.issues)
        self.assertEqual(len(result.accesses), 2)

    def test_caller_selected_contexts_remain_neutral(self):
        result = scan_paths("config.alpha || steps.beta.items.gamma", roots=("config", "steps"))
        self.assertFalse(result.issues)
        self.assertEqual(tuple(a.root for a in result.accesses), ("config", "steps"))
        self.assertEqual(tuple(s.literal_value for s in result.accesses[0].selectors), ("alpha",))
        self.assertEqual(scan_steps("config.alpha").accesses, ())

    def test_results_are_deeply_immutable_and_cache_is_syntax_only(self):
        result = scan_steps("steps.alpha.items.beta")
        with self.assertRaises(AttributeError):
            result.accesses[0].selectors[0].literal_value = "other"
        self.assertIs(scan_steps("steps.alpha.items.beta"), result)
        self.assertNotEqual(scan_steps("steps.other.items.beta"), result)
        self.assertTrue(scan_steps("steps[fn('x')").issues)
