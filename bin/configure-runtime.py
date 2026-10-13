#!/usr/bin/env python3
"""Adapt GitAgent 2.2.0's custom OpenAI model to the Responses API."""
from pathlib import Path
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


if __name__ == '__main__':
    configure(Path(sys.argv[1]))
