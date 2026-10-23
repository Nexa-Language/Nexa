# Author protocol 3.0

The transport is one JSON-RPC 2.0 object per newline over stdin/stdout. Requests carry an integer/string/null `id`; notifications omit it and receive no response. Each frame is limited to 2 Mi characters. Invalid oversized frames are drained before reading the following request. Clients should read the server's version and concurrency limit with `initialize`.

```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocol_version":"3.0","client":"editor"}}
```

At most two author resolutions run concurrently per server. `goal/resolve` returns an activity ID promptly. Poll `activity/read` for a terminal state; use `events/read` with the last received cursor for revision events. Shutdown requests cooperative cancellation and waits for active work within its existing deadline. A second client can durably cancel an activity through the same database.

| Method | Parameters | Result |
|---|---|---|
| `program/check` | `source`, optional `path` | CheckReport, source diagnostics and obligations |
| `revision/propose` | check parameters, `program_id`, nullable `expected_revision` | New source revision, or diagnostics |
| `goal/resolve` | `program_id`, `expected_revision`, `goal`, optional `input_json` and `budget` | `activity_id` |
| `activity/read` | `object_id` | AuthorActivity with bound revision and result |
| `activity/cancel` | `object_id` | Current activity after recording cancellation |
| `author/answer` | `program_id`, `expected_revision`, `request_id`, `answer` | Child revision with explicit author clarification |
| `events/read` | `program_id`, optional nonnegative `after` | Durable events and monotone cursors |
| `evidence/explain` | `object_id`, optional `context` | Evidence record and validity against the supplied context |

`author/answer` requires the current revision and its exact clarification ID. A concurrent edit produces `revision_conflict`. Proposed source is a draft; the CLI/shared `ProgramSession` builds and activates it with the current compiler environment. Runtime activities and author compilation activities occupy distinct namespaces. Runtime status/recovery and exact patch applications use `nexa open` or `ProgramSession`.

A client reads `error.data.code` for domain errors such as `revision_conflict`, `model_unavailable`, `author_busy` and `activity_missing`. Envelope errors use -32600; malformed parameters -32602; unknown methods -32601; domain errors -32000. Provider failures expose a sanitized failure kind. `nexa open schema author-protocol` supplies the generated request schema; the same frozen object models describe results.

An editor should present source diagnostics, open obligations, active revision, activity state, evidence validity and pending patch grants independently. Acceptance changes an implementation's status; the apply button requires the exact separately issued grant. The local author endpoint is intended for a trusted human/Agent client and is not an unauthenticated network service.
