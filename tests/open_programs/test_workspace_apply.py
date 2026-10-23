"""An admitted candidate still needs a specific, current workspace approval."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest


def proposal(tmp_path: Path, *, git: bool = False):
    from src.open_programs.model import AcceptancePolicy, Candidate, ContextSnapshot, EvidenceRecord, Implementation, Requirement, ResolutionResult
    from src.open_programs.store import ProgramStore
    from src.open_programs.workspace import WorkspaceManager, snapshot_workspace

    root = tmp_path / "repository"
    root.mkdir()
    (root / "a.txt").write_text("old-a\n")
    (root / "b.txt").write_text("old-b\n")
    if git:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
    snapshot = snapshot_workspace(root, ["a.txt", "b.txt", "new.txt"])
    payload = {"base_digest": snapshot.digest, "changes": [
        {"path": file.path, "before_digest": file.digest if file.content is not None else None, "content": "new-" + file.path + "\n"}
        for file in snapshot.files]}
    candidate = Candidate(goal_digest="repair", implementation=Implementation(kind="value", body=json.dumps(payload)))
    policy = AcceptancePolicy(name="fixture", requirements=(Requirement(name="type", kind="deterministic", checker_digest="fixed"),))
    context = ContextSnapshot(subject_digest=candidate.digest, policy_digest=policy.digest, task_id="task", now=time.time(), dependencies=())
    evidence = EvidenceRecord(requirement="type", kind="deterministic", subject_digest=candidate.digest, policy_digest=policy.digest,
                              task_id="task", issued_at=time.time(), dependencies=(), checker_digest="fixed", passed=True)
    result = ResolutionResult(goal_name="repair", status="accepted", candidate=candidate, context=context, policy=policy, evidence=(evidence,), output_json=json.dumps(payload))
    manager = WorkspaceManager(ProgramStore(tmp_path / "state.db"))
    patch = manager.prepare_patch(snapshot, result)
    return manager, patch, context, policy, root


@pytest.mark.parametrize("git", [False, True])
def test_approved_patch_is_exact_and_applies_once(tmp_path: Path, git: bool) -> None:
    manager, patch, context, policy, root = proposal(tmp_path, git=git)
    assert "-old-a" in patch.diff and "+new-a.txt" in patch.diff
    grant = manager.approve(patch, actor="operator")
    report = manager.apply_patch(patch, grant, context=context, policy=policy)
    assert report.state == "applied"
    assert (root / "a.txt").read_text() == "new-a.txt\n"
    before = (root / "a.txt").stat().st_mtime_ns
    assert manager.apply_patch(patch, grant, context=context, policy=policy) == report
    assert (root / "a.txt").stat().st_mtime_ns == before


def test_forged_revoked_expired_or_changed_approval_never_writes(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError

    manager, patch, context, policy, root = proposal(tmp_path)
    grant = manager.approve(patch, actor="operator")
    with pytest.raises(ProgramError, match="approval_invalid"):
        manager.apply_patch(patch, grant.model_copy(update={"actor": "forged"}), context=context, policy=policy)
    altered = patch.model_copy(update={"changes": patch.changes[:-1]})
    with pytest.raises(ProgramError, match="approval_mismatch"):
        manager.apply_patch(altered, grant, context=context, policy=policy)
    with pytest.raises(ProgramError, match="evidence_stale"):
        manager.apply_patch(patch, grant, context=context, policy=policy.model_copy(update={"name": "new-policy"}))
    manager.revoke(grant)
    with pytest.raises(ProgramError, match="approval_invalid"):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    expired = manager.approve(patch, actor="operator", expires_at=time.time() - 1)
    with pytest.raises(ProgramError, match="approval_expired"):
        manager.apply_patch(patch, expired, context=context, policy=policy)
    assert (root / "a.txt").read_text() == "old-a\n"
    assert not (root / "new.txt").exists()


def test_workspace_drift_and_symlink_substitution_preserve_user_data(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError

    manager, patch, context, policy, root = proposal(tmp_path)
    grant = manager.approve(patch, actor="operator")
    (root / "b.txt").write_text("user change")
    with pytest.raises(ProgramError, match="workspace_conflict"):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    assert (root / "a.txt").read_text() == "old-a\n"
    (root / "b.txt").unlink()
    outside = tmp_path / "outside.txt"
    outside.write_text("protected")
    (root / "b.txt").symlink_to(outside)
    with pytest.raises(ProgramError, match="unsafe_path"):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    assert outside.read_text() == "protected"


def test_interrupted_apply_is_reconciled_before_explicit_resume(tmp_path: Path, monkeypatch) -> None:
    from src.open_programs.model import ProgramError

    manager, patch, context, policy, root = proposal(tmp_path)
    grant = manager.approve(patch, actor="operator")
    write = manager._write_file
    def crash(*args, **kwargs):
        write(*args, **kwargs)
        raise SystemExit("after atomic write, before journal completion")
    monkeypatch.setattr(manager, "_write_file", crash)
    with pytest.raises(SystemExit):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    monkeypatch.setattr(manager, "_write_file", write)
    recovery = manager.recover(patch)
    assert recovery.state == "interrupted" and recovery.written == ("a.txt",)
    with pytest.raises(ProgramError, match="apply_interrupted"):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    result = manager.apply_patch(patch, grant, context=context, policy=policy, resume=True)
    assert result.state == "applied" and (root / "b.txt").read_text() == "new-b.txt\n"


@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", ".git/config", ".env", "a/../../outside", "a\\b"])
def test_snapshot_rejects_out_of_scope_and_sensitive_paths(tmp_path: Path, path: str) -> None:
    from src.open_programs.model import ProgramError
    from src.open_programs.workspace import snapshot_workspace

    with pytest.raises(ProgramError, match="unsafe_path"):
        snapshot_workspace(tmp_path, [path])


@pytest.mark.parametrize("target", ["a.txt", "new.txt"])
def test_process_death_after_file_link_is_recoverable(tmp_path: Path, target: str) -> None:
    import sys

    manager, patch, context, policy, root = proposal(tmp_path)
    grant = manager.approve(patch, actor="fixture-operator")
    payload = tmp_path / "crash-input.json"
    payload.write_text(json.dumps({"state": str(manager.store.path), "patch": patch.model_dump(mode="json"), "grant": grant.model_dump(mode="json"),
                                   "context": context.model_dump(mode="json"), "policy": policy.model_dump(mode="json")}))
    code = '''import json, os, sys
from pathlib import Path
from src.open_programs.model import PatchProposal, ApprovalGrant, ContextSnapshot, AcceptancePolicy
from src.open_programs.workspace import WorkspaceManager
from src.open_programs.store import ProgramStore
data = json.loads(Path(sys.argv[1]).read_text())
original = os.link
def die(*args, **kwargs):
 original(*args, **kwargs)
 if args[1] == sys.argv[2]:
  os._exit(86)
os.link = die
WorkspaceManager(ProgramStore(Path(data['state']))).apply_patch(PatchProposal.model_validate(data['patch']), ApprovalGrant.model_validate(data['grant']),
 context=ContextSnapshot.model_validate(data['context']), policy=AcceptancePolicy.model_validate(data['policy']))
'''
    child = subprocess.run([sys.executable, "-c", code, str(payload), target], check=False)
    assert child.returncode == 86
    assert (root / target).stat().st_nlink == 2
    report = manager.recover(patch)
    assert report.state == "interrupted" and target in report.written
    assert (root / target).stat().st_nlink == 1
    assert manager.apply_patch(patch, grant, context=context, policy=policy, resume=True).state == "applied"
    assert not list(root.glob(".nexa-write-*"))


@pytest.mark.parametrize("delete", [False, True])
def test_edit_at_replacement_boundary_is_retained(tmp_path: Path, monkeypatch, delete: bool) -> None:
    import os

    from src.open_programs.model import ProgramError

    manager, patch, context, policy, root = proposal(tmp_path)
    if delete:
        patch = patch.model_copy(update={"changes": (patch.changes[0].model_copy(update={"content": None}),)})
        manager.store.put(patch)
    grant = manager.approve(patch, actor="operator")
    injected = False

    def intercept(operation, *args, **kwargs):
        nonlocal injected
        if not injected and "src_dir_fd" in kwargs and "a.txt" in args[:2] or not injected and operation is unlink and args[0] == "a.txt":
            (root / "a.txt").write_text("concurrent-user-edit")
            injected = True
        return operation(*args, **kwargs)

    rename, replace, unlink = os.rename, os.replace, os.unlink
    monkeypatch.setattr(os, "rename", lambda *args, **kwargs: intercept(rename, *args, **kwargs))
    monkeypatch.setattr(os, "replace", lambda *args, **kwargs: intercept(replace, *args, **kwargs))
    monkeypatch.setattr(os, "unlink", lambda *args, **kwargs: intercept(unlink, *args, **kwargs))
    with pytest.raises(ProgramError, match="workspace_conflict"):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    assert injected
    recovery = manager.recover(patch)
    assert recovery.state == "conflict"
    retained = [root / item.recovery_path for item in recovery.preserved]
    assert any(path.read_text() == "concurrent-user-edit" for path in retained)


def test_new_failure_revokes_patch_admission(tmp_path: Path) -> None:
    from src.open_programs.model import ProgramError

    manager, patch, context, policy, root = proposal(tmp_path)
    grant = manager.approve(patch, actor="operator")
    manager.store.put(patch.evidence[0].model_copy(update={"passed": False, "issued_at": time.time()}))
    with pytest.raises(ProgramError, match="evidence_stale"):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    assert (root / "a.txt").read_text() == "old-a\n"


def test_death_after_retirement_restores_baseline_before_resume(tmp_path: Path, monkeypatch) -> None:
    import os

    manager, patch, context, policy, root = proposal(tmp_path)
    grant = manager.approve(patch, actor="operator")
    rename = os.rename

    def die(*args, **kwargs):
        rename(*args, **kwargs)
        raise SystemExit("after retirement")

    monkeypatch.setattr(os, "rename", die)
    with pytest.raises(SystemExit):
        manager.apply_patch(patch, grant, context=context, policy=policy)
    assert not (root / "a.txt").exists()
    monkeypatch.setattr(os, "rename", rename)
    recovery = manager.recover(patch)
    assert recovery.state == "interrupted" and recovery.written == ()
    assert (root / "a.txt").read_text() == "old-a\n"
    assert manager.apply_patch(patch, grant, context=context, policy=policy, resume=True).state == "applied"


def test_writes_through_old_descriptor_remain_recoverable(tmp_path: Path) -> None:
    manager, patch, context, policy, root = proposal(tmp_path)
    grant = manager.approve(patch, actor="operator")
    with (root / "a.txt").open("r+") as editor:
        result = manager.apply_patch(patch, grant, context=context, policy=policy)
        assert result.state == "applied"
        editor.seek(0)
        editor.write("late-editor-write")
        editor.truncate()
        editor.flush()
    recovered = manager.recover(patch)
    assert recovered.state == "conflict"
    assert (root / recovered.preserved[0].recovery_path).read_text() == "late-editor-write"
    assert (root / "a.txt").read_text() == "new-a.txt\n"


def test_cli_evidence_explanation_includes_new_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    import argparse

    from src.open_programs.commands import dispatch
    from src.open_programs.operations import ProgramSession

    manager, patch, context, policy, _ = proposal(tmp_path)
    failed = patch.evidence[0].model_copy(update={"passed": False, "issued_at": time.time()})
    manager.store.put(failed)
    monkeypatch.setattr(ProgramSession, "current_patch_context", lambda *args: (policy, context.model_copy(update={"now": time.time()})))
    environment = tmp_path / "env.json"
    environment.write_text(json.dumps({"image": "python@sha256:" + "a" * 64}))
    args = argparse.Namespace(open_command="evidence", state=str(manager.store.path), proposal_id=patch.digest, environment=str(environment))
    assert dispatch(args) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["admission"]["accepted"] is False
    assert failed.digest in data["admission"]["evidence_digests"]
