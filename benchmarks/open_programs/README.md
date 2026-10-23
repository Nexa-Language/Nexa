# Open Programs experiments

The harness uses public synthetic Python maintenance fixtures. Each sequence repairs a function, changes its requirement, then changes a settings dependency. `manifest.json` freezes 10 tasks (8 development, 2 held out), three trials, four variants, image identity and budgets. Held-out tasks are a small separate fixture split; they do not establish generalization to production repositories.

Configure the selected provider through the environment variable names in `examples/open_programs/maintain-aliyun.json`. Secrets are never included in reports. Use the source checkout and a running OCI backend with the pinned image already pulled:

```sh
uv run python -m benchmarks.open_programs.evaluate \
  --environment examples/open_programs/maintain-aliyun.json \
  --output /tmp/nexa-evaluation --workers 4
```

The output directory must be new. Each stage permits four model calls, 16,000 reported tokens and 90 seconds. A full run is capped at 1,440 calls and two million reported tokens. The shared meter counts in-flight calls; the summary's usage can temporarily exceed the cells already flushed. Final rows and meter totals must reconcile.

## Variants and interpretation

- `legacy_2_4`: the existing AgentRunner generates a Python implementation. A common external OCI evaluator, model review and exact workspace grant enforce the same acceptance boundary. This is an adapter for the fixture task, not a retrospective measurement of the released 2.4 product.
- `open_programs`: goal resolution with failure feedback and eligible local capsule reuse.
- `no_reuse`: the same resolution path, with generation repeated for each stage.
- `no_feedback`: failure feedback is omitted from implementation requests; the runtime still enforces all checks and grants.

Generation paths receive the same Patch output schema. Input snapshots, model, frozen oracle cases and stage limits are shared. There are no unaudited host edits. Successful model outputs still require fixture-operator approval before application. Approval counts describe the test driver, not human usability or approval latency.

The evidence-tracking ablation is a read-only counterfactual: run the previous accepted candidate against the changed input and oracle, then count cases that would fail if old success were assumed sufficient. Production evidence checks remain enabled. Counterfactual denominators include only stages with a previously accepted candidate; report them explicitly. The second matrix captured raw flags for any previous candidate; its published analysis excludes previously blocked/rejected candidates, and the driver now enforces this eligibility directly.

`summary.json` retains all stage rows; each sequence also saves the full resolution objects. `source-snapshot.json` maps implementation and harness paths to `content_digest(path.read_text())`: SHA-256 of the source text encoded as a canonical JSON string. The snapshot digest hashes that mapping. The final delivery manifest separately uses ordinary file-byte SHA-256. Record acceptance, failures, calls, input/output tokens, latency, reuse, oracle outcomes and unauthorized writes. Cost stays null until an applicable price schedule is verified.

## Six-stage demonstration

```sh
uv run python -m benchmarks.open_programs.flagship \
  --environment examples/open_programs/maintain-aliyun.json \
  --output /tmp/nexa-flagship
uv run pytest tests/open_programs/test_maintenance_e2e.py -q
```

The real demo includes author clarification, approved application, a separate controller process restart, goal/dependency revisions, reuse in another repository and a model-generated compiler advice pass with locked C1/C2 bootstrap. The test replays saved responses without a provider and runs actual OCI checks. Failed demo attempts and comparison rounds are retained in the execution record.

The first complete matrix lacked the Patch output schema in the 2.4 adapter and had 68 type-check failures in that group. It is retained as a protocol-development round. The corrected round supplies that schema and uses the reviewed implementation; its frozen source hash identifies the comparable results.

See the [measured results and methodological corrections](../../plan/evidence/2026-10-23-open-programs-experiment.md) and [all 360 corrected-round rows](../../plan/evidence/2026-10-23-open-programs-matrix-v2.json).
