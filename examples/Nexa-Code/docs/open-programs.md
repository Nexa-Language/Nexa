# Nexa 3.0 Open Programs integration

Nexa Code's existing 2.4 flows remain available. For the 3.0 maintenance path, use `../../open_programs/maintain.nx` with an explicit repository snapshot and a project-specific check environment. The shared CLI is `nexa run ... --repository ... --include ... --request ...`; it produces a proposal rather than applying immediately.

An author Agent or editor starts `nexa author` over stdio and negotiates protocol 3.0. Display CheckReport diagnostics and open goals, retain the revision returned by `revision/propose`, and send it with each resolve or clarification answer. Render deterministic checks and model reviews separately, including validity and dependency reasons. The runtime's source revision, active revision and each activity's pinned revision are distinct UI fields.

For patch review, show the exact diff and selected paths. A human action invokes `nexa open approve`; the apply action passes its returned grant ID and the current environment. Disable application on stale evidence, changed baseline or unresolved external effects. A model reply cannot synthesize a grant. Use `nexa open recover` for interrupted writes and ask the operator to select explicit resume after reviewing the partial state.

The maintained integration surface is the shared protocol plus JSON CLI. External editor repositories require their own interface update and verification; this repository provides schemas, example source, protocol documentation and executable fixture tests. See [usage](../../../docs/spec/3.0/usage.md) and [author protocol](../../../docs/spec/3.0/author-protocol.md).
