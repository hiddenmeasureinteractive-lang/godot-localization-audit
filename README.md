# Godot Localization Audit

**Find localization candidates. Review small patches. Catch broken translation placeholders.**

A local command-line tool for Godot developers preparing an existing game for more languages. It reads GDScript, separates recognizable translation calls and built-in UI patterns from text that needs review, and can propose `tr()` wrappers for display functions you explicitly choose.

**Early preview · Python 3.10+ · MIT · No runtime dependencies, accounts, API keys, or network calls.**

[Türkçe](docs/README.tr.md) · [Validation and limitations](docs/VALIDATION.md) · [Contributing](CONTRIBUTING.md)

## Start with a report

Clone this repository and run these commands from its directory:

```sh
git clone https://github.com/hiddenmeasureinteractive-lang/godot-localization-audit.git
cd godot-localization-audit
python -m godot_localization_audit scan /path/to/your/game
python -m godot_localization_audit scan /path/to/your/game --format json
```

The report includes file locations, reasons, and review categories. Scanning does not import or execute your project. It does not change source files.

Try the included synthetic project first:

```sh
python -m godot_localization_audit scan examples/tiny-godot --display-function show_message
python -m godot_localization_audit patch examples/tiny-godot --display-function show_message
python -m godot_localization_audit check-catalog examples/translations.csv
```

## Propose a small change

Suppose your game has a function `say(message)` that only displays dialogue:

```gdscript
say("The door is locked.")
```

Tell the tool that you want to review translation wrappers for that function:

```sh
python -m godot_localization_audit patch /path/to/your/game --display-function say > localization.patch
```

The proposed change is:

```diff
-say("The door is locked.")
+say(tr("The door is locked."))
```

The command writes a unified diff to standard output, **not to your source files**. Inspect the diff in your editor before applying it with your normal version-control workflow. Confirm that the named function displays text rather than storing keys, looking up resources, parsing commands, or comparing values. A name alone cannot prove that distinction. Run Godot and exercise the changed screens afterward.

Use a UTF-8 terminal when saving reports or patches. Windows PowerShell 5.1 redirection may use UTF-16; choose UTF-8 explicitly if your patch reader requires it.

## Check a translation CSV

```sh
python -m godot_localization_audit check-catalog /path/to/translations.csv
python -m godot_localization_audit check-catalog /path/to/translations.csv --format json
```

This checks structural translation problems, including formatting placeholders. It does not judge translation quality. Keep the source text in the first column; see the catalog limitations in the validation document before using key-based catalogs.

For example:

```csv
keys,en,tr
"Battery %d%%","Battery %d%%","Pil %d%%"
```

An opaque key such as `BATTERY_LABEL` cannot serve as the formatting baseline. This version has no source-locale selection option; use a source-text-key catalog for this check.

## Reading the results

| Category | Meaning |
| --- | --- |
| `candidate` | Narrow display-call pattern eligible for a proposed patch under your explicit allowlist |
| `review` | Text whose meaning or context needs manual inspection |
| `builtin` | A recognizable built-in extraction pattern; actual node type/settings still matter |
| `translated` | Inside a recognized Godot translation call; not a claim that a translation exists |
| `ignored` | A reason to avoid proposing a wrapper, such as a path, declaration, or `NO_TRANSLATE` comment |

`scan` returns exit code 0 when reading succeeds, even if review findings remain. `check-catalog` returns 1 for detected issues. Input errors return 2. `patch` without an allowlist returns an empty proposal; it never applies one.

Directory scanning skips generated/vendor folders including `.git`, `.godot`, `addons`, `build`, `dist`, `exports`, and `node_modules`. Symlinks and Windows reparse points are excluded. Inputs are limited to 2 MiB per file and 10,000 GDScript files. Exclusions and these limits mean a successful scan is not a completeness claim.

## Where it fits

Godot already provides [POT extraction](https://docs.godotengine.org/en/stable/tutorials/i18n/localization_using_gettext.html), translation resources, automatic translation for many UI properties, and pseudolocalization. This tool is a review aid alongside that workflow. It is not a replacement extraction engine, translation service, or localization framework.

| Need | Use |
| --- | --- |
| Generate POT files and load translations | Godot's built-in localization tools |
| Review text in an existing GDScript codebase | `scan` |
| Review wrappers for your own display function | `patch --display-function …` |
| Detect catalog formatting inconsistencies | `check-catalog` |
| Prove every screen is translated or readable | Playtesting and language review; not this tool |

## Designed for people and coding agents

Human-readable output helps with manual review; JSON exposes locations and reasons for editor integrations and coding agents. Treat findings as evidence to inspect, not authorization to modify a project. The scanner does not execute GDScript or send source text anywhere.

## Current boundaries

- This is a lexical review tool, not a full GDScript parser or type/data-flow analyzer.
- Initial support targets `.gd` source and CSV catalogs. It does not edit scenes, resources, PO files, C#, dialogue plugins, or imported assets.
- Dynamic strings, plural/context decisions, custom wrappers, and strings used both as display text and machine data need human review.
- Proposed changes are deliberately narrow. Reports may include false positives and miss text; no whole-game coverage or behavior-preservation guarantee is implied.
- No independent-project benchmark or measured productivity claim has been established yet. The current release is an early preview for feedback.

## Development

```sh
python -m unittest discover -s tests -v
```

See [validation](docs/VALIDATION.md) for the exact tested environment and optional Godot checks. Bug reports with a small synthetic GDScript example are especially useful. Please remove private dialogue, keys, and proprietary assets before posting.

Built by [Hidden Measure Interactive](https://github.com/hiddenmeasureinteractive-lang), from practical localization problems encountered while developing an independent Godot game. The repository contains synthetic examples rather than private game source or assets.
