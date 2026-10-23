"""Executable, separately versioned proposal for per-goal model call budgets."""

from __future__ import annotations

import json
from typing import Literal

from lark import Lark, UnexpectedInput
from pydantic import Field, ValidationError

from .compiler import OpenCompiler
from .frontend import _GRAMMAR, _nodes, _tokens, check
from .model import Dependency, FrozenModel, ProgramError, ProgramIR, ResolutionBudget, ResolutionResult, SourceBundle

GRAMMAR_ADDITION = '"budget" "model_calls" INT -> call_budget'
_EXTENSION_GRAMMAR = _GRAMMAR.replace('?goal_item: "stage" NAME -> stage', '?goal_item: ' + GRAMMAR_ADDITION + '\n          | "stage" NAME -> stage') + '\n%import common.INT\n'
_EXTENSION_PARSER = Lark(_EXTENSION_GRAMMAR, parser="lalr", propagate_positions=True, maybe_placeholders=False)


class GoalCallLimit(FrozenModel):
    goal: str
    max_model_calls: int = Field(ge=0, le=100)


class BudgetProgram(FrozenModel):
    schema_version: Literal["goal-call-budget.1"] = "goal-call-budget.1"
    language_version: Literal["3.1-budget"] = "3.1-budget"
    program: ProgramIR
    limits: tuple[GoalCallLimit, ...]


def upgrade_budget_program(source: str) -> BudgetProgram:
    report = check(SourceBundle(text=source))
    if not report.ok or report.program is None:
        raise ProgramError("extension_invalid", "Upgrade requires a valid 3.0 source program")
    return BudgetProgram(program=report.program, limits=())


def parse_budget_program(source: str) -> BudgetProgram:
    try:
        tree = _EXTENSION_PARSER.parse(source)
        versions = _nodes(tree, "version")
        if len(versions) != 1 or json.loads(_tokens(versions[0])[0]) != "3.1-budget":
            raise ProgramError("extension_invalid", "Opt in with language 3.1-budget")
        version = versions[0]
        replacements = [(version.meta.start_pos, version.meta.end_pos, 'language "3.0"')]
        limits = []
        for goal in _nodes(_nodes(tree, "program")[0], "goal"):
            clauses = _nodes(goal, "call_budget")
            if len(clauses) > 1:
                raise ProgramError("extension_invalid", "A goal can declare one call budget")
            for clause in clauses:
                limits.append(GoalCallLimit(goal=_tokens(goal)[0], max_model_calls=int(_tokens(clause)[0])))
                # Preserve line numbers for diagnostics of the lowered core program.
                padding = "".join("\n" if character == "\n" else " " for character in source[clause.meta.start_pos:clause.meta.end_pos])
                replacements.append((clause.meta.start_pos, clause.meta.end_pos, padding))
        lowered = source
        for start, end, text in sorted(replacements, reverse=True):
            lowered = lowered[:start] + text + lowered[end:]
        result = upgrade_budget_program(lowered)
        return result.model_copy(update={"limits": tuple(limits)})
    except (UnexpectedInput, ValidationError, ValueError) as error:
        if isinstance(error, ProgramError):
            raise
        raise ProgramError("extension_invalid", "Invalid syntax or call budget in the extension proposal") from error


def resolve_budget_goal(program: BudgetProgram, goal_name: str, compiler: OpenCompiler, *, budget: ResolutionBudget,
                        input_json: str = "{}") -> ResolutionResult:
    goal = next((goal for goal in program.program.goals if goal.name == goal_name), None)
    if goal is None:
        raise ProgramError("unknown_goal", goal_name)
    limit = next((limit.max_model_calls for limit in program.limits if limit.goal == goal_name), budget.max_model_calls)
    narrowed = budget.model_copy(update={"max_model_calls": min(limit, budget.max_model_calls)})
    if any(item.name == "language.extension" for item in compiler.environment.dependencies):
        raise ProgramError("extension_context_conflict", "An extension is already bound to this compiler environment")
    dependency = Dependency(name="language.extension", digest=program.digest)
    environment = compiler.environment.model_copy(update={"dependencies": (*compiler.environment.dependencies, dependency)})
    extended = OpenCompiler(environment, compiler.store, executor=compiler.executor, provider=compiler.provider)
    return extended.resolve_goal(goal, input_json=input_json, budget=narrowed)
