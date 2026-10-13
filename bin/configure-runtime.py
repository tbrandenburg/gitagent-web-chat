#!/usr/bin/env python3
"""Guarded compatibility fixes for the pinned GitAgent runtime."""
from pathlib import Path
import re
import sys


def configure(path: Path) -> None:
    original = 'api: "openai-completions",'
    replacement = ('api: provider === "openai" && modelId === "gpt-6-luna" '
                   '? "openai-responses" : "openai-completions",')
    source = path.read_text()
    if source.count(replacement) == 1:
        return
    if source.count(original) != 1:
        raise ValueError('Unexpected GitAgent loader; Responses adapter cannot be applied safely')
    path.write_text(source.replace(original, replacement))


def configure_auth(path: Path) -> None:
    marker = 'import { createHash, timingSafeEqual } from "node:crypto";'
    originals = ('const { createHash } = require("crypto");',
                 'const { timingSafeEqual } = require("crypto");')
    source = path.read_text()
    if source.count(marker) == 1 and not any(value in source for value in originals):
        return
    if any(source.count(value) != 1 for value in originals):
        raise ValueError('Unexpected GitAgent auth server; crypto imports cannot be adapted safely')
    updated = source
    for value in originals:
        updated, count = re.subn(r'^[ \t]*' + re.escape(value) + r'\n', '',
                                updated, flags=re.MULTILINE)
        if count != 1:
            raise ValueError('Unexpected GitAgent crypto declaration layout')
    path.write_text(marker + '\n' + updated)


def configure_text_chat(path: Path) -> None:
    replacements = (
        ('return loadUIHtml()',
         'return loadUIHtml().replace("@media (max-width: 700px)", "@media (max-width: 900px)")'),
        ('text: "Voice mode unavailable — no API key set. You can still chat via text.",',
         'text: "Text chat ready.",'),
        ('safeSend(browserWs, JSON.stringify({ type: "agent_done", result }));\n'
         '                            appendMessage(opts.agentDir, activeBranch, { type: "transcript", role: "assistant", text: result });',
         'sendToBrowser({ type: "transcript", role: "assistant", text: result });\n'
         '                            safeSend(browserWs, JSON.stringify({ type: "agent_done", result }));'),
        ('const url = new URL(req.url || "/", `http://localhost:${port}`);',
         'const url = new URL(req.url || "/", `http://localhost:${port}`);\n'
         '        if (url.pathname === "/favicon.ico") {\n'
         '            res.writeHead(204);\n'
         '            res.end();\n'
         '            return;\n'
         '        }'),
    )
    source = path.read_text()
    if all(source.count(updated) == 1 for _, updated in replacements):
        return
    if any(source.count(original) != 1 for original, _ in replacements):
        raise ValueError('Unexpected GitAgent text transport; compatibility fixes cannot be applied safely')
    for original, updated in replacements:
        source = source.replace(original, updated)
    path.write_text(source)


if __name__ == '__main__':
    configure(Path(sys.argv[1]))
    if len(sys.argv) > 2:
        configure_auth(Path(sys.argv[2]))
        configure_text_chat(Path(sys.argv[2]))
