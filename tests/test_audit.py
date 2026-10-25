"""Behavioral regression tests. Fixtures are invented, not extracted from a game."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def cli(*args):
    return subprocess.run([sys.executable, "-m", "godot_localization_audit", *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def apply_single_file_diff(original, patch):
    """Apply a one-file unified diff independently of the implementation."""
    import re
    old = original.splitlines(keepends=True)
    result, cursor, in_hunk = [], 0, False
    for line in patch.splitlines(keepends=True):
        if line.startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", line)
            if not match:
                raise AssertionError("Invalid unified hunk")
            start = int(match[1]) - 1
            result.extend(old[cursor:start])
            cursor, in_hunk = start, True
        elif in_hunk and line.startswith(" "):
            assert old[cursor] == line[1:]
            result.append(old[cursor]); cursor += 1
        elif in_hunk and line.startswith("-"):
            assert old[cursor] == line[1:]
            cursor += 1
        elif in_hunk and line.startswith("+"):
            result.append(line[1:])
    result.extend(old[cursor:])
    return "".join(result)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="audit-fixture-", dir=ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def source(self, source, name="main.gd"):
        path = self.path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def scan(self, source, *opts):
        path = self.source(source)
        before = path.read_bytes()
        proc = cli("scan", path, "--format", "json", *opts)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertEqual(path.read_bytes(), before)
        return json.loads(proc.stdout)["findings"]

    def test_explicit_display_function_has_patchable_candidate(self):
        rows = self.scan('extends Node\nfunc f():\n\tsay("Welcome aboard")\n', "--display-function", "say")
        self.assertTrue(any(r["text"] == "Welcome aboard" and r["patchable"] for r in rows))

    def test_unconfigured_call_is_not_patchable(self):
        rows = self.scan('extends Node\nfunc f():\n\twrite_data("Welcome aboard")\n')
        self.assertFalse(any(r["patchable"] for r in rows))

    def test_allowlist_does_not_rewrite_expression_or_member_calls(self):
        for expression in ['bus.say("Welcome aboard")', 'var value = say("Welcome aboard")',
                           'say("Welcome aboard" + suffix)', 'say("Welcome aboard", 3)',
                           'say("%d visitors" % count)']:
            with self.subTest(expression=expression):
                rows = self.scan('extends Node\nfunc f():\n\t' + expression + '\n', "--display-function", "say")
                self.assertFalse(any(r["patchable"] for r in rows))

    def test_static_functions_and_tool_scripts_abstain(self):
        for source in ['extends Node\nstatic func f():\n\tsay("Welcome aboard")\n',
                       'extends Node\nstatic func f(\n\targ = 3\n):\n\tsay("Welcome aboard")\n',
                       '@tool\nextends Node\nfunc f():\n\tsay("Welcome aboard")\n']:
            with self.subTest(source=source):
                rows = self.scan(source, "--display-function", "say")
                self.assertFalse(any(r["patchable"] for r in rows))

    def test_default_argument_not_patchable(self):
        rows = self.scan('extends Node\nfunc say(message = "Welcome aboard"):\n\tpass\n',
                         "--display-function", "say")
        self.assertFalse(any(r["patchable"] for r in rows))

    def test_builtin_text_does_not_need_wrapper(self):
        rows = self.scan('extends Node\nfunc f():\n\t$Label.text = "Welcome aboard"\n')
        self.assertTrue(any(r["category"] == "builtin" for r in rows))
        self.assertFalse(any(r["patchable"] for r in rows))

    def test_comments_are_not_candidates(self):
        rows = self.scan('# say("Never display this")\nextends Node\n', "--display-function", "say")
        self.assertFalse(any(r["patchable"] for r in rows))

    def test_escaped_quote_and_hash_stay_inside_literal(self):
        rows = self.scan('extends Node\nfunc f():\n\tsay("Hello \\"visitor\\" # room")\n'.replace('\\\\"', '\\"'), "--display-function", "say")
        self.assertEqual(sum(r["patchable"] for r in rows), 1)

    def test_single_quotes_supported(self):
        rows = self.scan("extends Node\nfunc f():\n\tsay('Welcome aboard')\n", "--display-function", "say")
        self.assertTrue(any(r["patchable"] for r in rows))

    def test_multiline_string_never_breaks_scanner(self):
        rows = self.scan('extends Node\nfunc f():\n\tsay("""First line\nSecond line""")\n', "--display-function", "say")
        self.assertTrue(any("First line" in r["text"] for r in rows))

    def test_regular_multiline_string_is_reported_but_not_patched(self):
        rows = self.scan('extends Node\nfunc f():\n\tsay("First line\nSecond line")\n',
                         "--display-function", "say")
        self.assertTrue(any("First line" in r["text"] for r in rows))
        self.assertFalse(any(r["patchable"] for r in rows))

    @unittest.skipUnless(os.environ.get("GODOT_BIN"), "Set GODOT_BIN to validate GDScript multiline syntax")
    def test_godot_accepts_regular_multiline_string(self):
        script = self.source('extends SceneTree\nfunc _initialize():\n\tvar message = "First line\nSecond line"\n\tassert(message.contains("Second line"))\n\tprint("MULTILINE_OK")\n\tquit(0)\n')
        self.source('config_version=5\n[application]\nconfig/name="Multiline Fixture"\n', 'project.godot')
        profile = self.path / 'profile'
        profile.mkdir()
        environment = os.environ.copy()
        environment.update(APPDATA=str(profile), LOCALAPPDATA=str(profile), XDG_DATA_HOME=str(profile))
        proc = subprocess.run([os.environ['GODOT_BIN'], '--headless', '--path', str(self.path),
                               '--log-file', str(self.path / 'godot.log'), '--script', str(script)],
                              capture_output=True, text=True, timeout=30, env=environment)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn('SCRIPT ERROR', proc.stderr)
        self.assertIn('MULTILINE_OK', proc.stdout)

    def test_machine_strings_not_patchable(self):
        for literal in ['&"Display group"', '^"Display node"', '$"Display node"',
                        'r"Raw display text"', '"res://Hello world.tscn"', '"user://Save data.json"']:
            with self.subTest(literal=literal):
                rows = self.scan(f'extends Node\nfunc f():\n\tsay({literal})\n', "--display-function", "say")
                self.assertFalse(any(r["patchable"] for r in rows))

    def test_existing_translation_calls_not_wrapped(self):
        for call in ['tr("Welcome aboard")', 'atr("Welcome aboard")', 'tr_n("One visitor", "Many visitors", n)', 'atr_n("One visitor", "Many visitors", n)']:
            with self.subTest(call=call):
                rows = self.scan(f'extends Node\nfunc f():\n\tsay({call})\n', "--display-function", "say")
                self.assertFalse(any(r["patchable"] for r in rows))

    def test_const_comparison_and_dictionary_are_not_patchable(self):
        for source in ['const KEY = "Display name"\n', 'var data = {"Display name": 3}\n', 'func f():\n\treturn "Display name" == name\n', 'func f():\n\treturn name in ["Display name"]\n']:
            with self.subTest(source=source):
                rows = self.scan('extends Node\n' + source, "--display-function", "say")
                self.assertFalse(any(r["patchable"] for r in rows))

    def test_no_translate_same_line_and_previous_line(self):
        for source in ['\tsay("Welcome aboard") # NO_TRANSLATE\n', '\t# NO_TRANSLATE\n\tsay("Welcome aboard")\n']:
            with self.subTest(source=source):
                rows = self.scan('extends Node\nfunc f():\n' + source, "--display-function", "say")
                self.assertFalse(any(r["patchable"] for r in rows))

    def test_patch_is_read_only_reviewable_and_idempotent(self):
        original = 'extends Node\nfunc f():\n\tsay("Welcome aboard")\n'
        path = self.source(original)
        result = cli("patch", path, "--display-function", "say")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_text(encoding="utf-8"), original)
        self.assertIn('tr("Welcome aboard")', result.stdout)
        changed = apply_single_file_diff(original, result.stdout)
        path.write_text(changed, encoding="utf-8")
        again = cli("patch", path, "--display-function", "say")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(again.stdout.strip(), "")

    def test_patch_without_allowlist_does_not_modify(self):
        path = self.source('extends Node\nfunc f():\n\tsay("Welcome aboard")\n')
        before = path.read_bytes()
        proc = cli("patch", path)
        self.assertEqual(before, path.read_bytes())
        self.assertNotIn('+\tsay(tr(', proc.stdout)

    @unittest.skipUnless(shutil.which('git'), 'Git needed for independent diff application')
    def test_patch_without_final_newline_applies_with_git(self):
        original = b'extends Node\nfunc f():\n\tsay("Welcome aboard")'
        path = self.path / 'main.gd'
        path.write_bytes(original)
        proc = cli('patch', path, '--display-function', 'say')
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(path.read_bytes(), original)
        patch = self.path / 'change.patch'
        patch.write_text(proc.stdout, encoding='utf-8', newline='\n')
        check = subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', '--check', str(patch)], cwd=self.path,
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        applied = subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)], cwd=self.path,
                                 capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(path.read_bytes(), b'extends Node\nfunc f():\n\tsay(tr("Welcome aboard"))')

    @unittest.skipUnless(shutil.which('git'), 'Git needed for independent diff application')
    def test_patch_preserves_bom_and_crlf_when_applied(self):
        original = b'\xef\xbb\xbfextends Node\r\nfunc f():\r\n\tsay("Welcome aboard")\r\n'
        path = self.path / 'main.gd'
        path.write_bytes(original)
        proc = subprocess.run([sys.executable, '-m', 'godot_localization_audit', 'patch',
                               str(path), '--display-function', 'say'], cwd=ROOT, capture_output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(path.read_bytes(), original)
        patch = self.path / 'change.patch'
        patch.write_bytes(proc.stdout)
        applied = subprocess.run(['git', '-c', 'core.autocrlf=false', 'apply', str(patch)],
                                 cwd=self.path, capture_output=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(path.read_bytes(), original.replace(b'say("Welcome aboard")', b'say(tr("Welcome aboard"))'))

    def test_scan_does_not_execute_project(self):
        path = self.source('extends Node\nfunc _init():\n\tOS.execute("malicious executable", [])\n')
        proc = cli("scan", path, "--format", "json")
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_generated_and_vendor_dirs_excluded(self):
        self.source('extends Node\n', 'main.gd')
        for folder in ['.git', '.godot', 'addons', 'build']:
            self.source('say("Never scan vendor code")\n', folder + '/vendor.gd')
        proc = cli("scan", self.path, "--format", "json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["files_scanned"], 1)

    def test_invalid_utf8_fails_explicitly(self):
        path = self.path / 'broken.gd'
        path.write_bytes(b'\xff\xfe\x00')
        proc = cli("scan", path, "--format", "json")
        self.assertNotEqual(proc.returncode, 0)

    def test_nonexistent_input_fails(self):
        self.assertNotEqual(cli("scan", self.path / 'missing', "--format", "json").returncode, 0)

    def test_unterminated_string_rejects_patch(self):
        path = self.source('extends Node\nfunc f():\n\tsay("Welcome aboard)\n')
        proc = cli("patch", path, "--display-function", "say")
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn('+++', proc.stdout)

    def test_symlink_is_not_followed(self):
        real = self.source('extends Node\nfunc f():\n\tsay("Welcome aboard")\n', 'outside.gd')
        link = self.path / 'link.gd'
        try:
            link.symlink_to(real)
        except OSError as exc:
            self.skipTest('OS does not permit test symlinks: ' + str(exc))
        proc = cli('patch', link, '--display-function', 'say')
        self.assertNotIn('+++', proc.stdout)

    def catalog(self, rows):
        path = self.path / "translations.csv"
        with path.open("w", encoding="utf-8", newline="") as stream:
            csv.writer(stream).writerows(rows)
        before = path.read_bytes()
        proc = cli("check-catalog", path, "--format", "json")
        self.assertEqual(path.read_bytes(), before)
        json.loads(proc.stdout)
        return proc

    def test_valid_catalog_escaped_percent(self):
        proc = self.catalog([['keys', 'en', 'tr'], ['Battery %d%%', 'Battery %d%%', 'Pil %d%%']])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_catalog_type_mismatch_detected(self):
        proc = self.catalog([['keys', 'en', 'tr'], ['Count %d', 'Count %d', 'Sayi %s']])
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_catalog_placeholder_order_detected(self):
        proc = self.catalog([['keys', 'en', 'tr'], ['%s: %d', '%s: %d', '%d: %s']])
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_catalog_missing_translation_detected(self):
        proc = self.catalog([['keys', 'en', 'tr'], ['Welcome', 'Welcome', '']])
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_catalog_named_placeholder_detected(self):
        proc = self.catalog([['keys', 'en', 'tr'], ['Welcome {player}', 'Welcome {player}', 'Merhaba {other}']])
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_catalog_dynamic_width_placeholder_detected(self):
        proc = self.catalog([['keys', 'en'], ['Count %*d', 'Count %d']])
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_catalog_named_placeholders_can_reorder(self):
        proc = self.catalog([['keys', 'en'], ['{first} {last}', '{last}, {first}']])
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_catalog_bbcode_tag_loss_detected(self):
        proc = self.catalog([['keys', 'en'], ['[b]Warning[/b]', 'Warning']])
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_catalog_schema_errors(self):
        for rows in [[['keys', 'en', 'en'], ['A', 'A', 'A']],
                     [['keys', 'en'], ['A', 'A'], ['A', 'A']],
                     [['keys', 'en'], ['A', 'A', 'extra']]]:
            with self.subTest(rows=rows):
                proc = self.catalog(rows)
                self.assertEqual(proc.returncode, 2, proc.stdout)

    @unittest.skipUnless(os.environ.get("GODOT_BIN"), "Set GODOT_BIN to run the optional engine smoke test")
    def test_godot_before_and_after_proposed_patch(self):
        project = self.path / "godot-project"
        shutil.copytree(ROOT / "examples" / "tiny-godot", project)
        script = project / 'main.gd'
        before = script.read_text(encoding="utf-8")
        profile = self.path / 'profile'
        profile.mkdir()
        environment = os.environ.copy()
        environment.update(APPDATA=str(profile), LOCALAPPDATA=str(profile), XDG_DATA_HOME=str(profile))
        command = [os.environ['GODOT_BIN'], '--headless', '--path', str(project),
                   '--log-file', str(self.path / 'godot.log'), '--', '--smoke']
        baseline = subprocess.run(command, capture_output=True, text=True, timeout=30, env=environment)
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        self.assertIn('LOCALIZATION_DEMO_OK', baseline.stdout)
        patch = cli('patch', script, '--display-function', 'show_message')
        self.assertEqual(patch.returncode, 0, patch.stderr)
        self.assertIn('tr(', patch.stdout)
        script.write_text(apply_single_file_diff(before, patch.stdout), encoding='utf-8')
        changed = subprocess.run(command, capture_output=True, text=True, timeout=30, env=environment)
        self.assertEqual(changed.returncode, 0, changed.stderr)
        self.assertNotIn('SCRIPT ERROR', changed.stderr)
        self.assertIn('LOCALIZATION_DEMO_OK', changed.stdout)
        translated = subprocess.run(command + ['--translated'], capture_output=True,
                                    text=True, timeout=30, env=environment)
        self.assertEqual(translated.returncode, 0, translated.stderr)
        self.assertNotIn('SCRIPT ERROR', translated.stderr)
        self.assertIn('LOCALIZATION_DEMO_OK', translated.stdout)


if __name__ == '__main__':
    unittest.main()
