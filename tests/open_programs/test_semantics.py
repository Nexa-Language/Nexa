"""Contracts for versioned programs, immutable inputs and legal transitions."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_program_rejects_unknown_versions_and_dependencies() -> None:
    from src.open_programs.model import GoalSpec, ProgramIR

    goal = GoalSpec(name="repair", return_type="Patch", intent="Repair", depends_on=("missing",))
    with pytest.raises(ValidationError, match="unknown_dependency"):
        ProgramIR(name="Maintenance", goals=(goal,))
    with pytest.raises(ValidationError):
        ProgramIR.model_validate({"name": "Maintenance", "language_version": "4.0"})


def test_program_rejects_cycles_and_duplicate_goal_names() -> None:
    from src.open_programs.model import GoalSpec, ProgramIR

    first = GoalSpec(name="one", return_type="Int", intent="First", depends_on=("two",))
    second = GoalSpec(name="two", return_type="Int", intent="Second", depends_on=("one",))
    with pytest.raises(ValidationError, match="goal_cycle"):
        ProgramIR(name="Cycle", goals=(first, second))
    with pytest.raises(ValidationError, match="duplicate_goal"):
        ProgramIR(name="Duplicate", goals=(second, second))


def test_semantic_identity_ignores_location_but_tracks_contract() -> None:
    from src.open_programs.model import GoalSpec, ProgramIR, SourceSpan

    goal = GoalSpec(name="answer", return_type="Int", intent="Return the answer", span=SourceSpan(path="one.nx", line=3, column=5))
    changed_location = goal.model_copy(update={"span": SourceSpan(path="two.nx", line=7, column=2)})
    program = ProgramIR(name="Demo", goals=(goal,))
    assert program.digest == ProgramIR(name="Demo", goals=(changed_location,)).digest
    assert program.digest != ProgramIR(name="Demo", goals=(goal.model_copy(update={"intent": "Different requirement"}),)).digest
    with pytest.raises(ValidationError):
        field = "intent"
        setattr(goal, field, "mutated")


@pytest.mark.parametrize(
    ("before", "after", "allowed"),
    [("open", "solving", True), ("evaluating", "satisfied", True), ("satisfied", "stale", True),
     ("stale", "solving", True), ("blocked", "solving", True), ("open", "satisfied", False),
     ("cancelled", "solving", False), ("satisfied", "open", False)],
)
def test_goal_transitions_require_evaluation(before: str, after: str, allowed: bool) -> None:
    from src.open_programs.model import GoalState, ProgramError, transition_goal

    if allowed:
        assert transition_goal(GoalState(before), GoalState(after)) == after
    else:
        with pytest.raises(ProgramError, match="invalid_transition"):
            transition_goal(GoalState(before), GoalState(after))


def test_checked_in_schema_validates_portable_fixture() -> None:
    from jsonschema import Draft202012Validator

    from src.open_programs.model import ProgramIR

    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "schemas/3.0/program.schema.json").read_text())
    fixture = json.loads((root / "tests/fixtures/open_programs/semantics.json").read_text())
    Draft202012Validator(schema).validate(fixture["program"])
    program = ProgramIR.model_validate_json(json.dumps(fixture["program"]))
    assert program.goals[0].stage == "runtime"
    assert program.goals[0].return_type == "Patch"
