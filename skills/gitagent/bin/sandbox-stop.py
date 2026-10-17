"""Signal only the recorded, same-boot, same-start-time supervisor."""
import json
import os
from pathlib import Path
import signal
import time


def stop(root: Path = Path('/var/tmp/gitagent-opencode')) -> None:
    file = root / 'supervisor.json'
    if not file.exists():
        return
    record = json.loads(file.read_text())
    pid = record['pid']
    if not isinstance(pid, int) or pid < 2 or pid == os.getpid():
        raise RuntimeError('Invalid owned PID')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    process = Path('/proc') / str(pid)

    def owned() -> bool:
        try:
            fields = (process / 'stat').read_text().split(') ')[1].split()
            command = (process / 'cmdline').read_bytes().split(b'\0')
            return (record['boot'] == boot and record['started'] == fields[19]
                    and b'/opt/agent/skills/gitagent/bin/sandbox-supervisor.mjs' in command
                    and fields[0] != 'Z')
        except FileNotFoundError:
            return False

    if not owned():
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + 12
    while owned() and time.monotonic() < deadline:
        time.sleep(0.1)
    if owned():
        raise RuntimeError('Owned supervisor did not shut down')


if __name__ == '__main__':
    try:
        stop()
    except (OSError, ValueError, KeyError, RuntimeError):
        raise SystemExit('Sandbox supervisor stop refused; no unrelated PID signaled') from None
