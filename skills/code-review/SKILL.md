---
name: code-review
description: Review supplied code or repository changes for actionable correctness and security defects; explicitly delegate security review only when requested.
confidence: 1
usage_count: 1
success_count: 1
failure_count: 0
negative_examples: []
---

# Code review

Read the relevant implementation and its tests. Report concrete findings with
severity, file references, impact, and a minimal fix. Avoid speculative style
complaints. When asked to delegate security review, invoke `security-reviewer`
through the runtime's subagent tool and summarize the actual child output.
If delegation is unavailable, say so instead of inventing a review transcript.
