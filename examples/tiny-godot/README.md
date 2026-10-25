# Tiny Godot example

This synthetic project contains one custom display function and one standard Godot `Button.text` assignment. It has no external assets.

From the repository root:

```sh
python -m godot_localization_audit scan examples/tiny-godot --display-function show_message
python -m godot_localization_audit patch examples/tiny-godot --display-function show_message
```

The second command prints a proposed diff; it does not apply it. Review the call to `show_message` and its implementation before applying the diff. The built-in button assignment needs no extra wrapper.

Open `project.godot` in Godot 4 to see the two controls. The test suite makes a disposable copy, applies the proposal independently, and verifies default-language behavior plus a programmatically supplied French translation. The `--translated` demo flag expects the proposed wrapper to have been applied first.
