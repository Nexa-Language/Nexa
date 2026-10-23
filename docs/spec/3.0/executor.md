# OCI execution contract

The Python controller uses the Docker CLI and the selected Docker context. It requires a pre-pulled image pinned by SHA-256. Failure to create, inspect or enforce the requested isolation returns an error; candidate execution has no host fallback.

Every candidate and repository check receives a new container: UID/GID 65534, no network, a read-only root filesystem, all capabilities dropped and `no-new-privileges`. There are no host bind mounts, home directories, model credentials or Docker socket. The writable `/tmp` is a 64 MiB tmpfs with `noexec,nosuid`. Source files and typed input travel through stdin. Repository commands run against the materialized snapshot; expected results stay in the host controller.

Default limits are one CPU, 128 MiB memory with the same total memory/swap limit, 64 PIDs, 30 seconds and 1 MiB captured output. Compiler calls also respect the remaining resolution deadline. The executor inspects Docker's applied configuration before running, caps captured output, and removes its unique container after success or failure. Cleanup failures are explicit.

`sandbox.exec` authorizes a Python `solve(inputs)` implementation. `repo.read` is required in both the goal and compiler environment before maintenance reads selected files. Repository checks also require `sandbox.write`. Arbitrary network access and candidate-side model RPC have no binding in 3.0.0. Model generation and review are host-controlled requests governed by the compiler budget.

Candidate stdout is untrusted. A parseable, typed result is an input to acceptance; fixed output oracles, independent repository checks and model review provide their own evidence. Editing repository tests does not change the host-owned expectations. See [Docker run options](https://docs.docker.com/reference/cli/docker/container/run/) for the underlying container controls.

Validation covers macOS with Colima and a trusted Linux test driver using the same Linux Docker Engine. The Linux driver has access to the engine socket to launch test candidates; candidates retain the isolation above. The evidence record identifies both images and reports this shared-engine topology. Independent hosted Linux CI remains a release gate.
