# Controlled compiler evolution

The first self-hosted component is a diagnostic advice pass. The fixed Python frontend still computes diagnostics and IR. A `.nx` goal supplies `solve(inputs)` for advice. Its input contains existing diagnostics and known goal names; its output contains only `{suggestions: [{code, replacement}]}`. The fixed core rejects suggestions for absent diagnostics or unknown names. An extension cannot delete errors, downgrade severity or grant capabilities.

`examples/open_programs/compiler_pass.nx` describes the pass as an open goal. The frozen `diagnostic-advice.v1` suite contains a real `repiar` / `repair` misspelling, an empty diagnostic set and a capability error which must receive no spelling suggestion. The C0 seed emits no suggestions and fails the misspelling case.

An EvolutionProposal binds the seed core hash, the proposed version, its program and artifact, the verifier digest and touched paths. The evaluator permits only `diagnostic_advice.py`. It runs the frozen corpus against C0 and C1, invokes the pass while C1 rebuilds its own locked artifact, extracts that rebuilt pass as C2, and compares C1/C2 IR, artifact identity, implementation identity and corpus observations. Bootstrap performs zero model generation calls. This is local bootstrap of one compiler pass; extending the Python core requires a separate proposal and evaluation boundary.

`EvolutionManager.initialize(seed)` registers the initial compiler. After `evaluate_evolution` stores a successful report, `nexa open compiler approve REPORT_ID --actor OPERATOR --state DB` issues an exact, expiring grant. `nexa open compiler select REPORT_ID --grant GRANT_ID --state DB` performs a seed CAS and records the selection event. `nexa open compiler check FILE --environment CONFIG --state DB` uses the selected advice pass while retaining original diagnostics. `status` shows its identity. A core/environment change requires reevaluation.

The six-stage flagship driver generates this pass through the configured live model, evaluates it and selects it under a named fixture operator. It records the report, grant relationship and normalized bootstrap result in its local state. Existing tests separately attempt verifier replacement, broader touched paths, seed changes and forged selection grants.

## Language extension proposal: goal call limits

`src/open_programs/extensions.py` contains the opt-in `3.1-budget` proposal, schema `goal-call-budget.1`. A goal can declare `budget model_calls N`, where N is 0–100. The lowering preserves the 3.0 core IR and source line positions, adds versioned per-goal limits and includes the extension identity in environment dependencies. Effective calls are `min(outer budget, goal limit)`.

`upgrade_budget_program` migrates valid 3.0 source without changing its semantic IR; absent clauses retain the outer budget. Duplicate/out-of-range clauses and unknown versions are rejected. Tests verify old-program equivalence and zero-call behavior. The proposal is invoked explicitly through `parse_budget_program` / `resolve_budget_goal`; stable `language "3.0"` parsing and CLI do not silently enable it. Publishing a new language version remains a separate release decision.
