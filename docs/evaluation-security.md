# Evaluation tooling security

Promptfoo is pinned at 0.124.1 with a lockfile. The `basic-ftp` transitive
dependency is overridden to 6.2.3 to address GHSA-c475-qrg2-pj4r without
changing the agent runtime or accepting npm's suggested Promptfoo downgrade.

At integration time, `npm audit` still reports high-severity findings through
`jks-js` / `node-forge` (GHSA-86w9-cpqp-85rv). The published `node-forge`
version checked was 1.4.0, still in the advisory range. Optional dependency
installation can also expose the `braces` advisory GHSA-vfj7-8cjw-p6xm;
the published version checked was 3.0.3. Re-run `npm audit` after `npm ci` for
the current complete installed/lockfile assessment. These are unresolved
toolchain risks, not a clean security bill of health.

This suite uses a local Python provider and deterministic assertions. It does
not use Java keystores, FTP, template watch mode, remote Promptfoo service
providers, or uploaded untrusted configurations. Do not expose `promptfoo view`
publicly, process untrusted config/templates, or interpret the unused feature
paths as proof the dependencies are safe. Upgrade when compatible patched
versions are published; review and re-run the suite after changing overrides.

Evaluation config, Python providers, JavaScript assertions, manifests, skills,
hooks, and sourced `.env` files are executable or instruction-bearing trusted
inputs. Run model-backed CI only via the explicitly triggered workflow on a
reviewed revision. Never pass model secrets to arbitrary pull-request code.

Results can contain repository content and complete tool outputs. They remain
ignored under `evals/results/`; review workflow artifact retention/access for
private data. Runtime permissions reduce tool authority but are not an OS
sandbox. Containers and model credentials must be limited separately.
