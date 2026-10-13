---
name: okf-knowledge
description: Consult, search, add, maintain, and validate project knowledge in the OKF bundle using progressive disclosure; use for project facts, previous decisions, and knowledge-base updates.
---
# Consult the OKF knowledge base

1. `knowledge/index.md` is already supplied in system context. Do not reload it unless updated.
2. Read the relevant nested `knowledge/<topic>/index.md` using the `read` tool.
3. Read only the matching concept Markdown with `read`. Follow links to other concepts if needed.
4. If the path is not obvious, call `cli` with `okf search "keywords"`; it returns paths, titles, summaries and trust/freshness indicators, **not all document bodies**. Read matches individually.
5. Cite `knowledge/<relative path>` in the answer. Check sources, `verified`, `status`, and `stale_after` before relying on contested claims.

# Maintain the bundle when requested

1. Search before creating duplicates.
2. Add or update a concept Markdown with YAML frontmatter; a non-empty `type` is required by OKF v0.2. Use provenance fields when known, and avoid invented verification.
3. Update the directory `index.md` and any parent navigation index if a new topic was added. `okf reindex --force` regenerates all indexes but **overwrites curated index prose**; use only when acceptable.
4. Run `cli` with `okf validate` and fix any structural failures.

References: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
