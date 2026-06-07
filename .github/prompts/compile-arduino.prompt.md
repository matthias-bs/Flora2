---
mode: agent
description: >
  Compile the current Arduino sketch using arduino-cli.
  Reads fqbn from .vscode/arduino.json and deduces the sketch path
  from the active editor file. Surfaces any compiler errors as inline
  diagnostics and explains them.
tools:
  - run_in_terminal
  - get_errors
  - read_file
---

# Compile Arduino Sketch

## What this skill does
1. Reads `.vscode/arduino.json` to obtain the `fqbn` (fully-qualified board name).  
2. Deduces the sketch folder from the currently active file: walks upward until a
  `.ino` file is found; falls back to `14_arduino/Flora2Arduino` if none is found.  
3. Invokes `.vscode/arduino-compile-runner.sh compile` (which calls the repo wrapper
   and then arduino-cli) and captures the output.  
4. Reports any errors or warnings as a numbered list referencing file + line.  
5. For each error, provides a brief explanation and a suggested fix.

## Parameters provided by the calling agent or user

| Name | Where it comes from |
|---|---|
| Active file path | Editor context (`${file}`) |
| Workspace root | `${workspaceFolder}` |

## Execution steps

Run the compile using the runner script. The `WORKSPACE_FOLDER` env variable is set
so the helper can find `arduino.json` without a hard-coded path:

```bash
WORKSPACE_FOLDER="${workspaceFolder}" \
  bash "${workspaceFolder}/.vscode/arduino-compile-runner.sh" compile \
  --active "${file}"
```

After the command finishes:
- Exit code 0 → report "Compilation succeeded" and the flash/RAM usage summary.
- Exit code non-zero → collect all lines matching `error:|warning:` and present them
  as an annotated list. Offer to open each offending file and jump to the problem line.

## Fallback behaviour

If `.vscode/arduino.json` is missing or contains no `fqbn`:
- Warn the user: "arduino.json not found or missing fqbn — using default ESP32 Dev Module".
- Use fallback: `esp32:esp32:esp32`.

## Not in scope for this skill
- Uploading to hardware (use the `upload-arduino` task or the `arduino-dev` agent).
- Serial monitoring.
