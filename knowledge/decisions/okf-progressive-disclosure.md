---
type: Architecture Decision
title: Progressive-disclosure OKF knowledge
description: Keep the navigation map in context and retrieve deeper knowledge only when relevant.
tags: [okf, knowledge, architecture, progressive-disclosure]
status: stable
sources:
  - resource: https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md
    title: Open Knowledge Format v0.2 specification
  - resource: https://github.com/open-gitagent/gitagent/blob/main/src/knowledge.ts
    title: GitAgent native knowledge loader
---

# Decision

Store durable project knowledge under `/agent/knowledge` as an OKF v0.2
bundle. The bundle root has an `index.md` and topic directories have their own
`index.md` files. GitAgent's separate native `knowledge/index.yaml` declares the
root `index.md` with `always_load: true` and lists topic indexes and concepts as
available on-demand documents. Individual concepts are not eagerly added to
every model prompt, and files omitted from this adapter are not exposed in the
loader's available-knowledge list.

# Retrieval policy

The agent reviews the root map on each task. When the question relates to
known topics, it reads the relevant topic index then only the concept documents
needed to answer. The `okf` utility provides `index`, `search`, `read`,
`validate` and `reindex` commands to aid navigation and curation.

# Trade-offs

- No vector database, embedding service or independent search server required.
- New concept files are visible to `okf search` without rebuilding an index.
- A human or agent must update its parent `index.md` for browsable navigation.
- Retrieval is *guided by the agent's prompt and available tools*, not a hard
  server-side guarantee that every relevant document was read.
