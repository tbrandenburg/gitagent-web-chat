# Pinned validation contracts

Source: [OpenGAP v0.5.0](https://github.com/open-gitagent/opengap/tree/d7a8e2edb54b942d6b4635cdd8b919ebd23e5da5/spec/schemas)
at commit `d7a8e2edb54b942d6b4635cdd8b919ebd23e5da5` (MIT).
`hooks.schema.json` and `memory.schema.json` are unchanged upstream copies.
`agent.schema.json` comes from `agent-yaml.schema.json` with two changes:

1. Repository-specific `$id`.
2. Optional `permissions` object and `$defs.permission_names`: a default effect
   and literal action lists (`allow`, `ask`, `deny`). Conflicting effects,
   including aliases, are rejected by the validator and exporter.

`cli` maps to OpenCode `shell`; `write` and `memory` map to `edit`.
Other actions retain their native names. `subagent` allow resolves only to
declared child IDs. Runtime enforcement is native OpenCode V2, not a claim
about upstream GitAgent browser chat. Upstream `opengap validate` may reject
the extension; use `make validate` with these pinned contracts.

OKF v0.2 is structurally validated by the portable `okf` utility, including
both bundles. This is not a complete provenance or attestation verifier.
Promptfoo uses its own published schema and native configuration validation;
it is not redefined in this directory.
