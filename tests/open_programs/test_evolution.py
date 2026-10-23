"""Compiler extensions pass a frozen evaluator and an actual partial bootstrap."""
from __future__ import annotations

from pathlib import Path

import pytest

IMAGE = "python@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704"
PASS = '''def solve(inputs):
 import difflib
 suggestions = []
 for diagnostic in inputs.get("diagnostics", []):
  if diagnostic["code"] != "unknown_goal":
   continue
  symbol = diagnostic["message"].split(":")[-1].strip()
  matches = difflib.get_close_matches(symbol, inputs.get("known_goals", []), n=1, cutoff=0.6)
  if matches:
   suggestions.append({"code": "unknown_goal", "replacement": matches[0]})
 return {"suggestions": suggestions}
'''


def setup(tmp_path: Path):
    from src.open_programs.compiler import OpenCompiler
    from src.open_programs.evolution import CompilerIdentity, EvolutionProposal, SemanticSuite, compiler_core_digest
    from src.open_programs.executor import OCIExecutor
    from src.open_programs.model import Candidate, CheckCase, CompilerEnvironment, GoalSpec, Implementation, OutputCheck, ProgramIR
    from src.open_programs.store import ProgramStore

    cases = (CheckCase(input_json='{"diagnostics":[{"code":"unknown_goal","message":"unknown_goal: repiar"}],"known_goals":["repair"]}',
                       expected_json='{"suggestions":[{"code":"unknown_goal","replacement":"repair"}]}'),
             CheckCase(input_json='{"diagnostics":[],"known_goals":["repair"]}', expected_json='{"suggestions":[]}'),
             CheckCase(input_json='{"diagnostics":[{"code":"capability_denied","message":"Forbidden"}],"known_goals":["repair"]}', expected_json='{"suggestions":[]}'))
    suite = SemanticSuite(name="diagnostic-advice.v1", cases=cases)
    environment = CompilerEnvironment(image=IMAGE, checks=(OutputCheck(name="checks.advice", cases=cases),))
    compiler = OpenCompiler(environment, ProgramStore(tmp_path / "state.db"), executor=OCIExecutor())
    goal = GoalSpec(name="advice", return_type="Json", intent="Suggest the closest known goal name for unknown_goal diagnostics; retain all original errors.",
                    capabilities=("sandbox.exec",), checks=("checks.advice",), implementation=Implementation(kind="python", body=PASS))
    program = ProgramIR(name="AdviceCompiler", goals=(goal,))
    lock = tmp_path / "advice.lock"
    artifact = compiler.build(program, lock_path=lock)
    seed_pass = Candidate(goal_digest="seed-advice", implementation=Implementation(kind="value", body='{"suggestions":[]}'))
    seed = CompilerIdentity(core_digest=compiler_core_digest(), pass_candidate=seed_pass, environment_digest=environment.digest, version="C0")
    proposal = EvolutionProposal(seed_digest=seed.digest, version="C1", program=program, artifact_digest=artifact.digest,
                                 pass_goal="advice", verifier_digest=suite.digest, touched_paths=("diagnostic_advice.py",))
    return compiler, seed, suite, proposal, lock


def test_pass_fixes_a_real_seed_failure_and_bootstraps_without_model(tmp_path: Path) -> None:
    from src.open_programs.evolution import evaluate_evolution

    compiler, seed, suite, proposal, lock = setup(tmp_path)
    report = evaluate_evolution(proposal, seed, suite, compiler, lock_path=lock)
    assert report.accepted, report.reasons
    assert report.seed_failures == (0,)
    assert report.candidate_failures == ()
    assert report.c1_artifact_digest == report.c2_artifact_digest
    assert report.c1_observations == report.c2_observations
    assert report.generation_requests == 0


@pytest.mark.parametrize("change", [{"verifier_digest": "weakened"}, {"touched_paths": ("acceptance.py",)}, {"seed_digest": "another-seed"}])
def test_evolution_cannot_change_its_evaluator_or_seed(tmp_path: Path, change: dict) -> None:
    from src.open_programs.evolution import evaluate_evolution

    compiler, seed, suite, proposal, lock = setup(tmp_path)
    report = evaluate_evolution(proposal.model_copy(update=change), seed, suite, compiler, lock_path=lock)
    assert not report.accepted


def test_selected_pass_adds_advice_without_downgrading_original_error(tmp_path: Path) -> None:
    from src.open_programs.evolution import AdvisoryCompiler, evaluate_evolution

    compiler, seed, suite, proposal, lock = setup(tmp_path)
    report = evaluate_evolution(proposal, seed, suite, compiler, lock_path=lock)
    source = '''language "3.0" program Repo(repo: Repository) {
      goal repair(change: ChangeRequest) -> Patch { stage runtime intent "Repair" }
      on change_request as request { let result = resolve repiar(request) propose repo.apply(result) requires human.approval }
    }'''
    assert report.compiler is not None
    response = AdvisoryCompiler(compiler, report.compiler).check(source)
    assert not response.check.ok
    assert response.check.diagnostics[0].code == "unknown_goal"
    assert tuple(item.model_dump() for item in response.suggestions) == ({"code": "unknown_goal", "replacement": "repair"},)


def test_compiler_selection_requires_an_exact_current_evolution_approval(tmp_path: Path) -> None:
    from src.open_programs.evolution import EvolutionManager, evaluate_evolution
    from src.open_programs.model import ProgramError

    compiler, seed, suite, proposal, lock = setup(tmp_path)
    report = evaluate_evolution(proposal, seed, suite, compiler, lock_path=lock)
    manager = EvolutionManager(compiler.store)
    manager.initialize(seed)
    grant = manager.approve(report, actor="fixture-operator")
    with pytest.raises(ProgramError, match="evolution_approval_invalid"):
        manager.select(report, grant.model_copy(update={"actor": "forged"}))
    assert manager.select(report, grant) == report.compiler
    with pytest.raises(ProgramError, match="compiler_selection_conflict"):
        manager.select(report, grant)
