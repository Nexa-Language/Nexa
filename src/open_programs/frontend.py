"""Offline parser and contract checker for the explicit Nexa 3.0 syntax."""

from __future__ import annotations

import ast
import json
from typing import cast, get_args

from lark import Lark, Token, Tree, UnexpectedInput
from pydantic import ValidationError

from .model import (
    CheckReport,
    Diagnostic,
    EventHandler,
    GoalSpec,
    Implementation,
    Parameter,
    PatchValue,
    ProgramError,
    ProgramIR,
    SourceBundle,
    SourceSpan,
    TypeName,
    canonical_json,
    content_digest,
)

_GRAMMAR = r'''
start: version? program
version: "language" STRING
program: "program" NAME parameters? "{" program_item* "}"
?program_item: "environment" NAME -> environment
             | "sandbox" NAME -> sandbox
             | "acceptance" NAME -> acceptance
             | goal | handler
parameters: "(" [parameter ("," parameter)*] ")"
parameter: NAME ":" NAME
goal: "goal" NAME parameters "->" NAME "{" goal_item* "}"
?goal_item: "stage" NAME -> stage
          | "intent" STRING -> intent
          | "context" path -> context
          | "capabilities" path_list -> capabilities
          | "depends" name_list -> depends
          | "ensure" path -> ensure
          | "review" "model" "(" STRING ")" -> review
          | "implementation" "open" -> impl_open
          | "implementation" "value" value -> impl_value
          | "implementation" "python" STRING -> impl_python
handler: "on" NAME "as" NAME "{" "let" NAME "=" "resolve" NAME "(" NAME ")" "propose" NAME "." "apply" "(" NAME ")" "requires" "human" "." "approval" "}"
path: NAME ("." NAME)*
path_list: "[" [path ("," path)*] "]"
name_list: "[" [NAME ("," NAME)*] "]"
?value: STRING -> string
      | SIGNED_NUMBER -> number
      | "true" -> true
      | "false" -> false
      | "null" -> null
      | "[" [value ("," value)*] "]" -> array
      | "{" [pair ("," pair)*] "}" -> object
pair: STRING ":" value
%import common.CNAME -> NAME
%import common.ESCAPED_STRING -> STRING
%import common.SIGNED_NUMBER
%import common.WS
%ignore WS
%ignore /\/\/[^\n]*/
'''
_PARSER = Lark(_GRAMMAR, parser="lalr", propagate_positions=True, maybe_placeholders=False)
Node = Tree[Token]


def _nodes(node: Node, kind: str | None = None) -> list[Node]:
    return [item for item in node.children if isinstance(item, Tree) and (kind is None or item.data == kind)]


def _tokens(node: Node) -> list[str]:
    return [str(item) for item in node.children if isinstance(item, Token)]


def _span(node: Node, source: SourceBundle) -> SourceSpan:
    return SourceSpan(path=source.path, line=node.meta.line, column=node.meta.column, end_line=node.meta.end_line, end_column=node.meta.end_column)


def _type(name: str) -> TypeName:
    if name not in get_args(TypeName):
        raise ProgramError("unknown_type", name)
    return cast(TypeName, name)


def _parameters(node: Node) -> tuple[Parameter, ...]:
    groups = _nodes(node, "parameters")
    if not groups:
        return ()
    return tuple(Parameter(name=_tokens(item)[0], type=_type(_tokens(item)[1])) for item in _nodes(groups[0]))


def _path(node: Node) -> str:
    return ".".join(_tokens(node))


def _literal_matches(value: object, expected: TypeName) -> bool:
    if expected == "Patch":
        try:
            PatchValue.model_validate(value)
            return True
        except ValidationError:
            return False
    types: dict[str, type | tuple[type, ...]] = {
        "Int": int, "Float": (int, float), "String": str, "Bool": bool,
        "Unit": type(None), "Patch": dict, "Repository": dict, "ChangeRequest": dict,
    }
    if expected == "Json":
        return True
    if expected in {"Int", "Float"} and isinstance(value, bool):
        return False
    return isinstance(value, types[expected])


def _implementation(node: Node, source: SourceBundle, expected: TypeName) -> Implementation | None:
    if node.data == "impl_open":
        return None
    if node.data == "impl_python":
        body = json.loads(_tokens(node)[0])
        try:
            module = ast.parse(body)
        except SyntaxError as error:
            raise ProgramError("invalid_implementation", str(error)) from error
        if not any(isinstance(item, ast.FunctionDef) and item.name == "solve" for item in module.body):
            raise ProgramError("invalid_implementation", "Python implementations must define solve(inputs)")
        return Implementation(kind="python", body=body)
    literal = _nodes(node)[0]
    value = json.loads(source.text[literal.meta.start_pos:literal.meta.end_pos])
    if not _literal_matches(value, expected):
        raise ProgramError("type_mismatch", f"Literal does not match {expected}")
    return Implementation(kind="value", body=canonical_json(value))


def _goal(node: Node, source: SourceBundle) -> GoalSpec:
    try:
        return _goal_fields(node, source)
    except ValidationError as error:
        field = error.errors()[0]["loc"][0] if error.errors()[0]["loc"] else ""
        origin = next((child for child in _nodes(node) if str(child.data) == field), node)
        message = "; ".join(item["msg"] for item in error.errors(include_input=False, include_url=False))
        raise ProgramError(_validation_code(error), message, object_id=_tokens(node)[0], span=_span(origin, source)) from error
    except ProgramError as error:
        error.span = error.span or _span(node, source)
        error.object_id = _tokens(node)[0]
        raise


def _goal_fields(node: Node, source: SourceBundle) -> GoalSpec:
    tokens = _tokens(node)
    output_type = _type(tokens[1])
    data: dict[str, object] = {"name": tokens[0], "return_type": output_type, "parameters": _parameters(node), "span": _span(node, source)}
    seen: set[str] = set()
    checks: list[str] = []
    reviews: list[str] = []
    for child in _nodes(node):
        kind = str(child.data)
        if kind == "parameters":
            continue
        key = "implementation" if kind.startswith("impl_") else kind
        if key not in {"ensure", "review"} and key in seen:
            raise ProgramError("duplicate_field", f"{tokens[0]}.{key}")
        seen.add(key)
        if kind.startswith("impl_"):
            data[key] = _implementation(child, source, output_type)
        elif kind in {"stage", "intent"}:
            data[kind] = json.loads(_tokens(child)[0]) if kind == "intent" else _tokens(child)[0]
        elif kind == "context":
            data[kind] = (_path(_nodes(child)[0]),)
        elif kind == "capabilities":
            data[kind] = tuple(_path(item) for item in _nodes(_nodes(child)[0]))
        elif kind == "depends":
            data["depends_on"] = tuple(_tokens(_nodes(child)[0]))
        elif kind == "ensure":
            checks.append(_path(_nodes(child)[0]))
        elif kind == "review":
            reviews.append(json.loads(_tokens(child)[0]))
    data.update(checks=tuple(checks), reviews=tuple(reviews))
    return GoalSpec.model_validate(data)


def _handler(node: Node, source: SourceBundle) -> EventHandler:
    event, parameter, result, goal, argument, repository, applied = _tokens(node)
    if argument != parameter or applied != result or result == parameter:
        raise ProgramError("binding_conflict", "Handler resolve/apply bindings must match and remain distinct", object_id=goal, span=_span(node, source))
    return EventHandler(event=event, parameter=parameter, result=result, goal=goal, repository=repository, span=_span(node, source))


def _program(node: Node, source: SourceBundle) -> ProgramIR:
    data: dict[str, object] = {"name": _tokens(node)[0], "parameters": _parameters(node)}
    for child in _nodes(node):
        kind = str(child.data)
        if kind not in {"environment", "sandbox", "acceptance"}:
            continue
        if kind in data:
            raise ProgramError("duplicate_field", kind)
        data[kind] = _tokens(child)[0]
    data["goals"] = tuple(_goal(child, source) for child in _nodes(node, "goal"))
    data["handlers"] = tuple(_handler(child, source) for child in _nodes(node, "handler"))
    program = ProgramIR.model_validate(data)
    _check_references(program)
    return program


def _check_references(program: ProgramIR) -> None:
    parameters = {parameter.name: parameter.type for parameter in program.parameters}
    if len(parameters) != len(program.parameters):
        raise ProgramError("duplicate_parameter", program.name)
    goals = {goal.name: goal for goal in program.goals}
    for goal in program.goals:
        for context in goal.context:
            name, _, member = context.partition(".")
            if parameters.get(name) != "Repository" or member != "snapshot":
                raise ProgramError("unknown_context", context, object_id=goal.name, span=goal.span)
        if goal.stage == "build" and any(goals[name].stage == "runtime" for name in goal.depends_on):
            raise ProgramError("stage_mismatch", "Build goal depends on runtime goal", object_id=goal.name, span=goal.span)
    for handler in program.handlers:
        if handler.goal not in goals:
            raise ProgramError("unknown_goal", handler.goal, object_id=handler.goal, span=handler.span)
        goal = goals[handler.goal]
        if goal.stage != "runtime":
            raise ProgramError("stage_mismatch", handler.goal, object_id=handler.goal, span=handler.span)
        if goal.return_type != "Patch" or len(goal.parameters) != 1 or goal.parameters[0].type != "ChangeRequest":
            raise ProgramError("type_mismatch", "Maintenance handlers require ChangeRequest -> Patch", object_id=handler.goal, span=handler.span)
        if parameters.get(handler.repository) != "Repository":
            raise ProgramError("unknown_repository", handler.repository, object_id=handler.goal, span=handler.span)


def _validation_code(error: ValidationError) -> str:
    for item in error.errors():
        if "capabilities" in item["loc"]:
            return "unknown_capability"
        for code in ("unknown_dependency", "goal_cycle", "duplicate_goal", "duplicate_parameter"):
            if code in item["msg"]:
                return code
    return "invalid_contract"


def check(source: SourceBundle) -> CheckReport:
    source_digest = content_digest(source.text)
    span = SourceSpan(path=source.path)
    try:
        tree = _PARSER.parse(source.text)
        versions = _nodes(tree, "version")
        if versions and json.loads(_tokens(versions[0])[0]) != source.language_version:
            raise ProgramError("unsupported_language", _tokens(versions[0])[0])
        node = _nodes(tree, "program")[0]
        span = _span(node, source)
        program = _program(node, source)
        return CheckReport(program=program, obligations=tuple(goal.name for goal in program.goals if goal.implementation is None), source_digest=source_digest)
    except UnexpectedInput as error:
        diagnostic = Diagnostic(code="syntax_error", message="Invalid Open Program syntax", span=SourceSpan(path=source.path, line=max(error.line, 1), column=max(error.column, 1)))
    except ValidationError as error:
        diagnostic = Diagnostic(code=_validation_code(error), message=str(error), span=span)
    except ProgramError as error:
        diagnostic = Diagnostic(code=error.code, message=str(error), span=error.span or span, obligation=error.object_id)
    except (ValueError, KeyError) as error:
        diagnostic = Diagnostic(code="invalid_literal", message=str(error), span=span)
    return CheckReport(diagnostics=(diagnostic,), source_digest=source_digest)


def diagnostic_context(source: SourceBundle, report: CheckReport) -> dict[str, object]:
    known = []
    try:
        tree = _PARSER.parse(source.text)
        program = _nodes(tree, "program")[0]
        known = [_tokens(goal)[0] for goal in _nodes(program, "goal")]
    except UnexpectedInput:
        # The report already carries syntax errors; malformed source has no reliable symbol table.
        pass
    return {"diagnostics": [diagnostic.model_dump(mode="json") for diagnostic in report.diagnostics], "known_goals": known}
