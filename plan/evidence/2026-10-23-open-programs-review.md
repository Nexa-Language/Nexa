# Open Programs whole-branch review and fixes

The fresh-context, read-only review covered all uncommitted and untracked 3.0 code against the approved plan. It returned four Important findings and no Critical findings. The reviewer reproduced each issue with local fixtures and controlled interleavings, without provider requests or credential access. This was one whole-branch review; subsequent verification used focused behavior regressions.

| Finding | Change | Behavior verified |
|---|---|---|
| Old locked evidence ignored a newer failure in the same context | Add a persistent evidence index, backfill old stores, merge current observations at admission | Locked build, runtime artifact admission, patch authorization, CLI explanation/export reject the old success; unrelated inputs remain independent; fresh checks can restore acceptance |
| Maintenance read and sent repository content before checking `repo.read` | Check both goal and environment before snapshot construction | Empty or mismatched grants produce zero snapshot calls and zero provider calls |
| Capsule reuse replaced a source-declared explicit implementation | Check implementation equality during matching and at `resolve_goal(candidate=...)` | Both capsule and direct API reject the mismatched candidate |
| User edits in the last check/replace window were overwritten | Journal a retained-original location, move and inspect the old inode, install by exclusive link | Replacement/deletion interleavings preserve user content; recovery handles retirement and install interruptions; late writes through an old descriptor remain recoverable |

The initial regressions failed on all nine targeted cases. Their fixes passed; two additional CLI consumers were then covered by failing tests and corrected. Final focused verification: **28 passed** on Python 3.12, with corresponding Python 3.10/3.14 and Linux checks recorded in the validation ledger.

Workspace originals remain in journal-referenced `.nexa-preserved-*/original` files. The caller decides when to archive or delete them. This provides recovery for observed races; file-name switching has a short gap and multi-file application is journaled rather than one filesystem transaction. `recover` reports differences, including writes to a retired inode after application.

Logs: `.superpowers/sdd/03-v1-nexa-3-open-programs/t9-review-red.log`, `t9-cli-current-evidence-red.log`, `t9-final-cli-boundaries.log`, `t9-final-python310-cli.log`, `t9-final-python314-cli.log`, `t9-linux-cli.log`. The [source snapshot](2026-10-23-open-programs-source.json) identifies the reviewed-and-repaired implementation for reproduction.
