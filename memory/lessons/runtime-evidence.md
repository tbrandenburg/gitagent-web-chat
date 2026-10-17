---
type: Lesson Learned
title: Runtime evidence
description: Distinguish definition checks from actual runtime evidence.
tags: [memory, testing]
status: draft
sources:
  - resource: https://github.com/tbrandenburg/gitagent-web-chat/blob/main/README.md
    title: Existing runtime testing boundaries
---

# Lesson

Offline validation checks the agent definition; it does not demonstrate model
responses, tool execution, or delegation. Run a live check and retain its
result before claiming those behaviors work. This is a documented testing
principle, not a record of a fabricated debugging session.
