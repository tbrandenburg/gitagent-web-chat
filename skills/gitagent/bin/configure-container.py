#!/usr/bin/env python3
"""Adapt only the pinned voice server's container port and bind address."""
from pathlib import Path
import sys


PORT = 'const port = opts.port || 3333;'
CONTAINER_PORT = '''const portValue = process.env.PORT ?? "3333";
    if (!/^[0-9]{1,5}$/.test(portValue) || portValue.trim() !== portValue || Number(portValue) < 1 || Number(portValue) > 65535) {
        throw new Error("PORT must be an integer between 1 and 65535");
    }
    const port = Number(portValue);'''
LISTEN = 'httpServer.listen(port, () => resolve());'
CONTAINER_LISTEN = 'httpServer.listen(port, "0.0.0.0", () => resolve());'


def configure(path: Path) -> None:
    source = path.read_text()
    replacements = ((PORT, CONTAINER_PORT), (LISTEN, CONTAINER_LISTEN))
    if all(source.count(updated) == 1 and original not in source
           for original, updated in replacements):
        return
    if any(source.count(original) != 1 or updated in source
           for original, updated in replacements):
        raise ValueError('Unexpected voice server; container adapter not applied')
    updated = source
    for original, replacement in replacements:
        updated = updated.replace(original, replacement)
    path.write_text(updated)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: configure-container.py /path/to/voice/dist/server.js')
    try:
        configure(Path(sys.argv[1]))
    except (OSError, ValueError):
        sys.exit('Container adapter failed: unexpected or inaccessible voice server')
