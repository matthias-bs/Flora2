#!/usr/bin/env python3
"""
arduino_compile_helper.py

Helper to determine `fqbn` and sketch path and invoke arduino-cli (or the repo wrapper).

Behavior:
Behavior:
- Reads `.vscode/arduino.json` for `fqbn` and `sketch` when present.
- If `--fqbn` is provided it overrides arduino.json.
- If `--active` is provided, it searches upwards for the nearest `.ino` file and uses that sketch folder.
- Falls back to `14_arduino/Flora2Arduino` when no sketch can be deduced.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _enforce_huge_app_partition(fqbn: str) -> str:
    # Enforce ESP32 partition menu option for larger sketch binaries.
    # If PartitionScheme is missing, append it. If present, override it.
    if not fqbn or not fqbn.startswith('esp32:'):
        return fqbn

    parts = fqbn.split(':', 3)
    if len(parts) < 3:
        return fqbn

    if len(parts) == 3:
        return fqbn + ':PartitionScheme=huge_app'

    opts = [o for o in parts[3].split(',') if o]
    replaced = False
    for i, opt in enumerate(opts):
        if opt.startswith('PartitionScheme='):
            opts[i] = 'PartitionScheme=huge_app'
            replaced = True
            break
    if not replaced:
        opts.append('PartitionScheme=huge_app')

    return ':'.join(parts[:3]) + ':' + ','.join(opts)


def read_arduino_json(workspace):
    path = Path(workspace) / '.vscode' / 'arduino.json'
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def find_nearest_ino(active_path: Path, workspace: Path):
    p = active_path if active_path.is_dir() else active_path.parent
    while True:
        inos = list(p.glob('*.ino'))
        if inos:
            return p
        if p == workspace or p.parent == p:
            break
        p = p.parent
    return None


def find_wrapper(workspace: Path):
    w = workspace / '.vscode' / 'arduino-cli-wrapper.sh'
    if w.exists() and os.access(str(w), os.X_OK):
        return str(w)
    if w.exists():
        return str(w)
    return None


def _is_relevant_compile_line(line: str) -> bool:
    s = line.strip()
    if not s:
        return False

    # Keep final memory/result summary lines (German + English variants).
    final_prefixes = (
        "Der Sketch verwendet",
        "Globale Variablen verwenden",
        "Sketch uses",
        "Global variables use",
    )
    if s.startswith(final_prefixes):
        return True

    # Keep diagnostics.
    low = s.lower()
    if " warning:" in low or low.startswith("warning:"):
        return True
    if " error:" in low or low.startswith("error:"):
        return True
    if "fehler" in low:
        return True
    if "undefined reference" in low:
        return True

    return False


def _run_with_compile_filter(cmd):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True,
    )

    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        if _is_relevant_compile_line(line):
            print(line)

    return proc.wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['compile', 'upload', 'monitor'])
    parser.add_argument('--fqbn', help='Override fqbn', default=None)
    parser.add_argument('--port', help='Serial port', default=None)
    parser.add_argument('--config', help='Extra config', default=None)
    parser.add_argument('--active', help='Active file path (to deduce sketch)', default=None)
    args, extras = parser.parse_known_args()

    workspace = Path(os.environ.get('WORKSPACE_FOLDER', os.getcwd())).resolve()
    arduino_cfg = read_arduino_json(workspace)

    fqbn = args.fqbn or arduino_cfg.get('fqbn') or arduino_cfg.get('board')
    if not fqbn:
        fqbn = 'esp32:esp32:esp32'
        print('arduino.json not found or missing fqbn; using default ESP32 Dev Module.', file=sys.stderr)
    fqbn = _enforce_huge_app_partition(fqbn)

    sketch_dir = None

    if args.active:
        active = Path(args.active).resolve()
        sketch_dir = find_nearest_ino(active, workspace)

    if not sketch_dir:
        sketch_entry = arduino_cfg.get('sketch')
        if sketch_entry:
            cand = (workspace / sketch_entry).resolve()
            if cand.exists():
                sketch_dir = cand if cand.is_dir() else cand.parent

    if not sketch_dir:
        sketch_dir = workspace / '14_arduino' / 'Flora2Arduino'
    sketch_path = str(sketch_dir)

    wrapper = find_wrapper(workspace)
    extras = [e for e in extras if e != '--']

    if wrapper:
        cmd = ['bash', wrapper, args.action]
    else:
        cmd = ['arduino-cli', args.action]

    if fqbn:
        if args.action == 'compile':
            print(f'Using FQBN: {fqbn}', file=sys.stderr)
        cmd += ['--fqbn', fqbn]
    if args.port:
        cmd += ['--port', args.port]
    if args.config:
        cmd += ['--config', args.config]
    if args.action == 'compile':
        cmd.append(sketch_path)
    if extras:
        cmd += extras

    try:
        if args.action == 'compile':
            sys.exit(_run_with_compile_filter(cmd))
        sys.exit(subprocess.run(cmd).returncode)
    except FileNotFoundError:
        print('arduino-cli or wrapper not found.', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
