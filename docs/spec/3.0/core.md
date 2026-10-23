# Open Programs 3.0 core contract

Version: Nexa 3.0.0 Python reference implementation. This document defines the supported Open Programs maintenance subset; persisted objects and the author protocol carry separate schema versions.

## Language and compilation

Use `language "3.0"` followed by `program Name(parameters) { ... }`. The canonical `compile_program` API dispatches explicit versions; existing `compile_source` and `compile_file` retain their 2.4 Python-lowering contract. `nexa check file.nx --json` parses and checks Open Programs without creating a provider.

A goal declares parameters, a return type, a nonempty intent, and optional stage, context, capabilities, checks, reviews and dependencies. Supported boundary types are Int, Float, String, Bool, Unit, Json, Patch, Repository and ChangeRequest. JSON-encoded values are checked at the boundary; arbitrary Python implementations are checked inside OCI before their results become usable.

`implementation open` leaves an obligation. `implementation value <JSON>` supplies a literal; `implementation python "..."` supplies a Python function `solve(inputs)` executed only inside OCI. Build goals default to stage build; event-triggered goals use stage runtime. Build goals cannot depend on runtime goals. Dependencies form a DAG and are available to implementations in `inputs["dependencies"]`.

The initial handler is `on event as request { let result = resolve goal(request) propose repo.apply(result) requires human.approval }`. It requires a Repository parameter and a runtime goal with ChangeRequest input and Patch output. This is the maintenance subset; unsupported syntax produces a source diagnostic.

## Identity and lifecycle

Immutable program IR, candidate, policy and evidence objects carry deterministic SHA-256 identities over canonical JSON. Source spans remain serialized but are excluded from semantic identity. Source content is hashed separately. The portable program schema is in `schemas/3.0/program.schema.json`.

Goals transition open → solving → evaluating → satisfied. Blocked goals can resume solving. Relevant dependency changes make satisfied goals stale. Cancelled goals are terminal. Completion requires evidence; skipping directly from open to satisfied is invalid.

A source revision is distinct from an activated runtime revision. Author edits commit source revisions with compare-and-swap. Runtime admission and workspace application have separate records and gates.

## Evidence

An evidence record binds the candidate, policy, checker, dependencies, task, issue time and optional expiry. Evidence validity is independent of whether the check passed. Revocation, expiry, future timestamps, changed inputs and changed policy invalidate reuse. Mutable model aliases require a new review in a different task. Human decisions are task-bound.

Every policy requires at least one uniquely named check. Its required dependency set must be present in the evidence. A newer failure prevents an older success from satisfying the same requirement. Deterministic checks and model reviews remain separate records.

OutputCheck runs candidates in OCI against frozen JSON oracles. RepositoryCheck applies a typed patch to the selected source snapshot in a fresh OCI container, runs controller-owned commands and compares their exit code and output with host-held expectations. Candidate code cannot replace those expectations by editing repository tests. Model reviews use a separate structured boolean result. Named environment, sandbox and acceptance declarations currently select the reference bindings; actual check requirements are explicit goal clauses and the environment configuration.

## Persistence and replay

SQLite uses a dedicated application ID and schema namespace. Revision updates, object insertion and events commit in one transaction. Unknown schemas and unrelated databases are rejected before migration. Immutable objects are verified against their digest when read.

A lock binds the program, compiler version, environment and stored artifact. Locked builds revalidate evidence and issue no generation requests. New model sampling creates a new artifact. Model budgets cap call counts and requested output tokens; reported input/output usage is accumulated, and a missing usage report blocks acceptance. Provider token accounting can be observed only after the request completes.
