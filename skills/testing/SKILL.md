---
name: testing
description: Select and run high-signal repository regression checks and distinguish offline checks from live model evaluations.
---

# Testing

Use `make lint test validate doctor` for offline checks. Use `npm ci` and
`npm run eval:validate` for Promptfoo configuration. Run `make eval` on the host
against the intended OpenCode container for real model regressions, only when
token usage is authorized. Test invalid inputs and permission denials too.
Report runner summaries; a configured test is not an executed test.
