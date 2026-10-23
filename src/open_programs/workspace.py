"""Explicit workspace snapshots, exact grants and recoverable per-file application."""

from __future__ import annotations

import difflib
import os
import stat
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from .evidence import current_evidence, evaluate_policy
from .model import (
    AcceptancePolicy,
    ApplyResult,
    ApprovalGrant,
    ApprovalState,
    ContextSnapshot,
    FileChange,
    PatchProposal,
    PatchValue,
    PreservedFile,
    ProgramError,
    ProgramEvent,
    ResolutionResult,
    SnapshotFile,
    WorkspaceSnapshot,
)
from .store import ProgramStore


def _safe_path(path: str) -> tuple[str, ...]:
    parts = PurePosixPath(path).parts
    protected = {".git", ".nexa", ".superpowers", ".ssh", ".aws", "secrets.nxs", "node_modules", ".venv"}
    if (not parts or path != "/".join(parts) or path.startswith("/") or "\\" in path or "\x00" in path
            or any(part in {".", ".."} or part in protected or part.startswith((".env", ".nexa-write-", ".nexa-preserved-")) for part in parts)):
        raise ProgramError("unsafe_path", "Patch paths must be explicit relative project files outside protected locations")
    return parts


@contextmanager
def _root_fd(root: str, identity: tuple[int, int] | None = None) -> Generator[int, None, None]:
    try:
        descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as error:
        raise ProgramError("unsafe_path", "Workspace root must be a real directory") from error
    try:
        info = os.fstat(descriptor)
        if identity is not None and (info.st_dev, info.st_ino) != identity:
            raise ProgramError("workspace_conflict", "Workspace directory identity changed")
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _parent_fd(root: int, path: str) -> Generator[tuple[int, str], None, None]:
    parts = _safe_path(path)
    descriptor = os.dup(root)
    try:
        for part in parts[:-1]:
            following = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = following
        yield descriptor, parts[-1]
    except OSError as error:
        raise ProgramError("unsafe_path", "Path parent is missing, inaccessible or a symlink") from error
    finally:
        os.close(descriptor)


def _read_file(root: int, path: str) -> SnapshotFile:
    with _parent_fd(root, path) as (parent, name):
        try:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        except FileNotFoundError:
            return SnapshotFile(path=path, content=None)
        except OSError as error:
            raise ProgramError("unsafe_path", "Only regular project files may be read") from error
        with os.fdopen(descriptor, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1048576:
                raise ProgramError("unsafe_path", "Expected one regular file of at most 1 MiB without hard links")
            content = handle.read(1048577)
            if len(content) > 1048576:
                raise ProgramError("snapshot_limit", "File grew beyond the snapshot limit")
            try:
                return SnapshotFile(path=path, content=content.decode("utf-8"), mode=stat.S_IMODE(info.st_mode))
            except UnicodeDecodeError as error:
                raise ProgramError("unsupported_file", "Initial patch format requires UTF-8 text") from error


def snapshot_workspace(root: Path, paths: list[str]) -> WorkspaceSnapshot:
    if not paths or len(paths) > 512 or len(paths) != len(set(paths)):
        raise ProgramError("snapshot_scope", "Select between 1 and 512 distinct project files")
    for path in paths:
        _safe_path(path)
    absolute = str(root.absolute())
    with _root_fd(absolute) as descriptor:
        info = os.fstat(descriptor)
        files = tuple(_read_file(descriptor, path) for path in sorted(paths))
    if sum(len((file.content or "").encode()) for file in files) > 10485760:
        raise ProgramError("snapshot_limit", "Selected source exceeds 10 MiB")
    return WorkspaceSnapshot(root=absolute, device=info.st_dev, inode=info.st_ino, files=files)


def patched_files(base: WorkspaceSnapshot, patch: PatchValue) -> tuple[SnapshotFile, ...]:
    if patch.base_digest != base.digest:
        raise ProgramError("workspace_conflict", "Patch baseline differs from the supplied repository")
    files = {file.path: file for file in base.files}
    if len(files) != len(base.files):
        raise ProgramError("snapshot_scope", "Duplicate file paths")
    for file in base.files:
        _safe_path(file.path)
    for change in patch.changes:
        _safe_path(change.path)
        before = files.get(change.path)
        if before is None or change.before_digest != (before.digest if before.content is not None else None):
            raise ProgramError("patch_scope", "Patch does not match the selected repository files")
        if change.content is not None and len(change.content.encode()) > 1048576:
            raise ProgramError("patch_limit", "Patch file exceeds 1 MiB")
        files[change.path] = SnapshotFile(path=change.path, content=change.content, mode=before.mode)
    return tuple(files[name] for name in sorted(files))


class WorkspaceManager:
    def __init__(self, store: ProgramStore) -> None:
        self.store = store

    def prepare_patch(self, base: WorkspaceSnapshot, result: ResolutionResult) -> PatchProposal:
        if result.status != "accepted" or result.candidate is None or result.policy is None or result.context is None:
            raise ProgramError("candidate_unaccepted", "Patch preparation requires accepted evidence")
        context = result.context.model_copy(update={"now": time.time()})
        if (context.subject_digest != result.candidate.digest
                or not evaluate_policy(result.policy, current_evidence(self.store, list(result.evidence), context), context).accepted):
            raise ProgramError("evidence_stale", "Revalidate the candidate before proposing its patch")
        value = PatchValue.model_validate_json(result.output_json)
        patched_files(base, value)
        if value.base_digest != base.digest:
            raise ProgramError("workspace_conflict", "Candidate was produced against another baseline")
        files = {file.path: file for file in base.files}
        differences = []
        for change in value.changes:
            _safe_path(change.path)
            before = files.get(change.path)
            if before is None or change.before_digest != (before.digest if before.content is not None else None):
                raise ProgramError("patch_scope", "Patch must match a selected file and its exact baseline")
            if change.content is not None and len(change.content.encode()) > 1048576:
                raise ProgramError("patch_limit", "Patch file exceeds 1 MiB")
            differences.extend(difflib.unified_diff((before.content or "").splitlines(keepends=True), (change.content or "").splitlines(keepends=True),
                                                    fromfile="a/" + change.path, tofile="b/" + change.path))
        proposal = PatchProposal(baseline=base, candidate_digest=result.candidate.digest, changes=value.changes, policy_digest=result.policy.digest,
                                 evidence=result.evidence, task_id=context.task_id, diff="".join(differences))
        self.store.put(proposal)
        return proposal

    def approve(self, proposal: PatchProposal, *, actor: str, expires_at: float | None = None) -> ApprovalGrant:
        self.store.get(proposal.digest, PatchProposal)
        now = time.time()
        grant = ApprovalGrant(actor=actor, proposal_digest=proposal.digest, baseline_digest=proposal.baseline.digest, policy_digest=proposal.policy_digest,
                              evidence_digests=tuple(record.digest for record in proposal.evidence), scope=tuple(change.path for change in proposal.changes),
                              task_id=proposal.task_id, issued_at=now, expires_at=expires_at if expires_at is not None else now + 3600)
        self.store.set_reference("approval:" + grant.digest, None, ApprovalState(grant=grant))
        return grant

    def revoke(self, grant: ApprovalGrant) -> None:
        state = self.store.reference("approval:" + grant.digest, ApprovalState)
        if state is None:
            raise ProgramError("approval_invalid", "Unknown grant")
        self.store.set_reference("approval:" + grant.digest, state.digest, state.model_copy(update={"revoked": True}))

    def _authorize(self, proposal: PatchProposal, grant: ApprovalGrant, context: ContextSnapshot, policy: AcceptancePolicy) -> None:
        registered = self.store.reference("approval:" + grant.digest, ApprovalState)
        if registered is None or registered.revoked:
            raise ProgramError("approval_invalid", "A registered, unrevoked approval is required")
        if (grant.proposal_digest != proposal.digest or grant.baseline_digest != proposal.baseline.digest or grant.policy_digest != proposal.policy_digest
                or grant.evidence_digests != tuple(record.digest for record in proposal.evidence) or grant.task_id != proposal.task_id
                or grant.scope != tuple(change.path for change in proposal.changes)):
            raise ProgramError("approval_mismatch", "Approval does not cover this exact patch")
        now = time.time()
        if now >= grant.expires_at or now < grant.issued_at:
            raise ProgramError("approval_expired", "Obtain a current approval")
        current = context.model_copy(update={"now": now})
        if (policy.digest != proposal.policy_digest or current.subject_digest != proposal.candidate_digest or current.task_id != proposal.task_id
                or not evaluate_policy(policy, current_evidence(self.store, list(proposal.evidence), current), current).accepted):
            raise ProgramError("evidence_stale", "Patch evidence does not satisfy the current acceptance context")

    def _check_baseline(self, descriptor: int, proposal: PatchProposal, written: tuple[str, ...]) -> None:
        changes = {change.path: change for change in proposal.changes}
        for file in proposal.baseline.files:
            expected = file
            if file.path in written:
                expected = self._target(file, changes[file.path])
            if _read_file(descriptor, file.path) != expected:
                raise ProgramError("workspace_conflict", "A selected file changed after proposal or during application")

    def _target(self, before: SnapshotFile, change: FileChange) -> SnapshotFile:
        return SnapshotFile(path=change.path, content=change.content, mode=before.mode if change.content is not None else 0o644)

    def apply_patch(self, proposal: PatchProposal, grant: ApprovalGrant, *, context: ContextSnapshot,
                    policy: AcceptancePolicy, resume: bool = False) -> ApplyResult:
        with self.store.lease("workspace:" + proposal.baseline.root):
            self._authorize(proposal, grant, context, policy)
            previous = self.store.reference("apply:" + proposal.digest, ApplyResult)
            if previous and previous.state == "applied":
                return previous
            if previous and previous.state in {"applying", "interrupted"} and not resume:
                raise ProgramError("apply_interrupted", "Inspect recovery and explicitly resume the partial patch")
            if previous and previous.state == "conflict":
                raise ProgramError("workspace_conflict", "Create a new proposal for the current workspace")
            written = previous.written if previous else ()
            base = proposal.baseline
            with _root_fd(base.root, (base.device, base.inode)) as descriptor:
                self._check_baseline(descriptor, proposal, written)
                journal = ApplyResult(proposal_digest=proposal.digest, grant_digest=grant.digest, state="applying", written=written,
                                      preserved=previous.preserved if previous else ())
                self.store.set_reference("apply:" + proposal.digest, previous.digest if previous else None, journal)
                return self._apply(descriptor, proposal, grant, context, policy, journal)

    def _apply(self, descriptor: int, proposal: PatchProposal, grant: ApprovalGrant, context: ContextSnapshot,
               policy: AcceptancePolicy, journal: ApplyResult) -> ApplyResult:
        baseline = {file.path: file for file in proposal.baseline.files}
        for change in proposal.changes:
            if change.path in journal.written:
                continue
            self._authorize(proposal, grant, context, policy)
            preserved = None
            if baseline[change.path].content is not None:
                location = PurePosixPath(change.path).parent / (".nexa-preserved-" + uuid.uuid4().hex) / "original"
                preserved = PreservedFile(path=change.path, recovery_path=str(location))
            pending = journal.model_copy(update={"pending_path": change.path, "pending_temporary": ".nexa-write-" + uuid.uuid4().hex,
                                                  "preserved": (*journal.preserved, preserved) if preserved else journal.preserved})
            self.store.set_reference("apply:" + proposal.digest, journal.digest, pending)
            self._write_file(descriptor, baseline[change.path], change, temporary=pending.pending_temporary, preserved=preserved)
            completed = pending.model_copy(update={"written": (*pending.written, change.path), "pending_path": "", "pending_temporary": ""})
            self.store.set_reference("apply:" + proposal.digest, pending.digest, completed)
            journal = completed
        self._check_baseline(descriptor, proposal, journal.written)
        completed = journal.model_copy(update={"state": "applied"})
        self.store.set_reference("apply:" + proposal.digest, journal.digest, completed,
                                 events=[(proposal.task_id, ProgramEvent(kind="patch_applied", object_id=completed.digest, detail=grant.digest))])
        return completed

    def _write_file(self, root: int, before: SnapshotFile, change: FileChange, *, temporary: str, preserved: PreservedFile | None) -> None:
        if _read_file(root, change.path) != before:
            raise ProgramError("workspace_conflict", "File changed immediately before writing")
        with _parent_fd(root, change.path) as (parent, name):
            if change.content is None:
                if before.content is not None:
                    assert preserved is not None
                    self._preserve_file(parent, name, before, preserved)
                os.fsync(parent)
                return
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                with os.fdopen(descriptor, "wb") as handle:
                    handle.write(change.content.encode())
                    os.fchmod(handle.fileno(), before.mode)
                    handle.flush()
                    os.fsync(handle.fileno())
                if _read_file(root, change.path) != before:
                    raise ProgramError("workspace_conflict", "File changed while preparing the atomic replacement")
                if before.content is not None:
                    assert preserved is not None
                    self._preserve_file(parent, name, before, preserved)
                try:
                    os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                except FileExistsError as error:
                    raise ProgramError("workspace_conflict", "Another writer created the destination; the previous file is retained") from error
                os.fsync(parent)
            finally:
                try:
                    os.unlink(temporary, dir_fd=parent)
                except FileNotFoundError:
                    pass

    def _preserved_directory(self, item: PreservedFile) -> str:
        original = PurePosixPath(item.path)
        location = PurePosixPath(item.recovery_path)
        directory = location.parent.name
        if location.name != "original" or location.parent.parent != original.parent or not directory.startswith(".nexa-preserved-"):
            raise ProgramError("apply_corrupt", "Invalid retained file location")
        return directory

    def _preserve_file(self, parent: int, name: str, before: SnapshotFile, item: PreservedFile) -> None:
        directory = self._preserved_directory(item)
        os.mkdir(directory, 0o700, dir_fd=parent)
        backup = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            os.fsync(parent)
            try:
                os.rename(name, "original", src_dir_fd=parent, dst_dir_fd=backup)
            except FileNotFoundError as error:
                raise ProgramError("workspace_conflict", "Another writer removed the destination") from error
            os.fsync(backup)
            os.fsync(parent)
            retained = _read_file(backup, "original").model_copy(update={"path": before.path})
            if retained != before:
                raise ProgramError("workspace_conflict", "Concurrent edit retained at " + item.recovery_path)
        finally:
            os.close(backup)

    def recover(self, proposal: PatchProposal) -> ApplyResult:
        with self.store.lease("workspace:" + proposal.baseline.root):
            previous = self.store.reference("apply:" + proposal.digest, ApplyResult)
            if previous is None:
                raise ProgramError("apply_missing", "Patch application has not started")
            before = {file.path: file for file in proposal.baseline.files}
            written = []
            conflict = False
            base = proposal.baseline
            with _root_fd(base.root, (base.device, base.inode)) as descriptor:
                self._recover_temporary(descriptor, previous)
                for item in previous.preserved:
                    change = next(change for change in proposal.changes if change.path == item.path)
                    conflict |= not self._recover_preserved(descriptor, item, before[item.path], change)
                for change in proposal.changes:
                    current = _read_file(descriptor, change.path)
                    if current == self._target(before[change.path], change):
                        written.append(change.path)
                    elif current != before[change.path]:
                        conflict = True
            state = "conflict" if conflict else "applied" if previous.state == "applied" else "interrupted"
            result = previous.model_copy(update={"state": state, "written": tuple(written),
                                                  "pending_path": "", "pending_temporary": ""})
            self.store.set_reference("apply:" + proposal.digest, previous.digest, result)
            return result

    def _recover_preserved(self, root: int, item: PreservedFile, before: SnapshotFile, change: FileChange) -> bool:
        with _parent_fd(root, item.path) as (parent, target):
            try:
                backup = os.open(self._preserved_directory(item), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            except FileNotFoundError:
                return True
            try:
                try:
                    info = os.stat("original", dir_fd=backup, follow_symlinks=False)
                except FileNotFoundError:
                    return True
                if info.st_nlink == 2:
                    other = os.stat(target, dir_fd=parent, follow_symlinks=False)
                    if (info.st_dev, info.st_ino) != (other.st_dev, other.st_ino):
                        raise ProgramError("workspace_conflict", "Retained file has an unexpected hard link")
                    os.unlink("original", dir_fd=backup)
                    os.fsync(backup)
                    return _read_file(root, item.path) == before
                retained = _read_file(backup, "original").model_copy(update={"path": item.path})
                if retained != before:
                    return False
                if change.content is not None and _read_file(root, item.path).content is None:
                    # Restore a known baseline after death between retirement and installation.
                    try:
                        os.link("original", target, src_dir_fd=backup, dst_dir_fd=parent, follow_symlinks=False)
                    except FileExistsError:
                        return False
                    os.fsync(parent)
                    os.unlink("original", dir_fd=backup)
                    os.fsync(backup)
                return True
            finally:
                os.close(backup)

    def _recover_temporary(self, root: int, journal: ApplyResult) -> None:
        name = journal.pending_temporary
        if not name:
            return
        if not name.startswith(".nexa-write-") or "/" in name or "\\" in name:
            raise ProgramError("apply_corrupt", "Invalid journal temporary name")
        with _parent_fd(root, journal.pending_path) as (parent, target):
            try:
                info = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                return
            if not stat.S_ISREG(info.st_mode) or info.st_nlink not in {1, 2}:
                raise ProgramError("workspace_conflict", "Journal temporary was replaced")
            if info.st_nlink == 2:
                other = os.stat(target, dir_fd=parent, follow_symlinks=False)
                if (info.st_dev, info.st_ino) != (other.st_dev, other.st_ino):
                    raise ProgramError("workspace_conflict", "Unexpected hard link during recovery")
            # Only the random name persisted before this write may be cleaned up.
            os.unlink(name, dir_fd=parent)
            os.fsync(parent)
