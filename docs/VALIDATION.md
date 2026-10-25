# Validation and limits

## Reproduce

From a source checkout with Python 3.10 or later:

```sh
python -m unittest discover -s tests -v
```

For the two optional real-engine tests, set `GODOT_BIN` to a Godot 4 executable before running the command. For example, in PowerShell:

```powershell
$env:GODOT_BIN = 'C:/Tools/Godot.exe'
python -m unittest discover -s tests -v
```

Git must be installed to exercise independent unified-diff application. Tests use disposable fixtures under `tests/`; the CLI itself does not write or execute project files. Engine subprocesses use isolated data directories and log files. Tests do not require network access or a model API.

## Observed local result

On 25 October 2026, the suite ran on Windows with Godot **4.7.1.stable.official.a13da4feb**:

- **36 tests executed: 35 passed, 1 skipped.**
- The symlink fixture was skipped because Windows did not grant permission to create a symbolic link. This result does not prove the symlink boundary on Windows; it must also run in an environment that permits symlinks.
- Real Godot accepted the synthetic demo before the proposed patch, after independent patch application, and with a French translation selected after patching. Each run exited successfully and emitted its expected marker.
- A separate real-engine fixture confirmed that ordinary quoted GDScript strings may contain literal line breaks. Such strings are reported but not proposed for rewriting.
- Git applied proposed diffs to files without a final newline and to UTF-8 BOM / CRLF files. Those byte-level properties were preserved with `core.autocrlf=false`.

Regression cases cover existing translation calls; StringName and NodePath literals; raw strings; comments; `NO_TRANSLATE`; static functions; tool scripts; defaults; constants; machine paths; ambiguous and compound calls; second-run idempotence; malformed input; and catalog placeholder / schema errors.

## What this does not establish

This is an early preview tested with synthetic fixtures. It is not a GDScript type checker, complete parser, translation quality evaluator, or proof of gameplay behavior preservation. No claim of zero false positives across arbitrary projects follows from this suite. An allowlisted function may still store its argument as a machine key: only the project maintainer can establish that it is display-only.

The demo has two controls and one translated message. It does not establish coverage of dialogue trees, dynamic text, replay, accessibility text, rare screens, plural behavior, every locale, or entire games. Catalog checks do not verify BBCode attributes or linguistic correctness.

Before calling this a generally validated migration tool, evaluate three independent licensed Godot projects against their built-in POT extraction baseline. Record false edits, missed display text, abstentions, parser results, second-run changes, visited-screen coverage, and actual human review time separately. Publish those results without copying private game content.
