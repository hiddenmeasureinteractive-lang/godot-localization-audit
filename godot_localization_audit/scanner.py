"""A lexical audit, deliberately not a GDScript parser or data-flow analyzer."""
from __future__ import annotations

from dataclasses import dataclass
import difflib
import os
from pathlib import Path
import re
from typing import Iterable

MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_FILES = 10000
SKIP_DIRS = {".git", ".godot", ".hg", ".svn", ".venv", "venv", "node_modules",
             "addons", "build", "builds", "dist", "export", "exports", "vendor"}
TRANSLATORS = {"tr", "tr_n", "atr", "atr_n"}
BUILTIN_PROPERTIES = {"text", "placeholder_text", "tooltip_text"}
BUILTIN_METHODS = {"set_text", "add_item", "add_tab", "set_tab_title"}


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    start: int
    end: int


def _tokens(source: str) -> list[Token]:
    result = []
    i = 0
    while i < len(source):
        c = source[i]
        if c.isspace() or (i == 0 and c == "\ufeff"):
            i += 1
            continue
        start = i
        if c == "#":
            end = source.find("\n", i)
            i = len(source) if end == -1 else end
            result.append(Token("comment", source[start:i], start, i))
        elif c in "\"'":
            delimiter = c * 3 if source.startswith(c * 3, i) else c
            i += len(delimiter)
            while i < len(source):
                if source[i] == "\\":
                    i += 2
                elif source.startswith(delimiter, i):
                    i += len(delimiter)
                    break
                else:
                    i += 1
            else:
                raise ValueError(f"unterminated string at offset {start}")
            result.append(Token("string", source[start:i], start, i))
        elif c.isalpha() or c == "_":
            i += 1
            while i < len(source) and (source[i].isalnum() or source[i] == "_"):
                i += 1
            result.append(Token("identifier", source[start:i], start, i))
        else:
            two = source[i:i + 2]
            i += 2 if two in {"==", "!=", "<=", ">=", ":=", "->", "&&", "||"} else 1
            result.append(Token("symbol", source[start:i], start, i))
    return result


def _body(token: Token) -> str:
    quote_len = 3 if token.text.startswith(('"""', "'''")) else 1
    # Preserve escapes exactly; reporting and patching never re-encode the literal.
    return token.text[quote_len:-quote_len]


def _validate_functions(functions: Iterable[str]) -> set[str]:
    names = set(functions)
    if any(not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name) for name in names):
        raise ValueError("display functions must be bare ASCII GDScript identifiers")
    if names & (TRANSLATORS | BUILTIN_METHODS):
        raise ValueError("built-in translation/display methods do not need custom wrapping")
    return names


def _static_ranges(source: str) -> list[tuple[int, int]]:
    """Conservative indentation ranges; false suppression is preferable to edits."""
    lines = source.splitlines(keepends=True)
    offsets = []
    position = 0
    for line in lines:
        offsets.append(position)
        position += len(line)
    result = []
    for i, line in enumerate(lines):
        if not re.match(r"\s*static\s+func\b", line):
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        end = len(source)
        for j in range(i + 1, len(lines)):
            other = lines[j]
            if not other.strip() or other.lstrip().startswith("#"):
                continue
            # Closing parentheses of a multiline signature may be dedented;
            # only a new peer declaration ends this conservative range.
            if len(other) - len(other.lstrip(" \t")) <= indent and re.match(
                    r"\s*(?:(?:static\s+)?func\b|class\b|var\b|const\b|signal\b|enum\b|@)", other):
                end = offsets[j]
                break
        result.append((offsets[i], end))
    return result


def scan_source(source: str, path: str = "source.gd", display_functions: Iterable[str] = ()) -> list[dict]:
    """Return literal findings; malformed strings raise ValueError.

    Patch eligibility requires a whole standalone call to an explicitly trusted
    display function, with exactly one literal argument. This cannot establish
    what that user-defined function does: the allowlist is a user contract.
    """
    allowed = _validate_functions(display_functions)
    all_tokens = _tokens(source)
    tokens = [t for t in all_tokens if t.kind != "comment"]
    comments = [t for t in all_tokens if t.kind == "comment"]
    static_ranges = _static_ranges(source)
    tool_script = any(t.text == "@" and i + 1 < len(tokens) and tokens[i + 1].text == "tool"
                      for i, t in enumerate(tokens))
    findings = []
    stack: list[tuple[str, str]] = []
    statement_start = 0
    for index, token in enumerate(tokens):
        previous = tokens[index - 1] if index else None
        if previous and not stack and ("\n" in source[previous.end:token.start] or previous.text == ";"):
            statement_start = index
        if token.kind == "string":
            body = _body(token)
            line_start = source.rfind("\n", 0, token.start) + 1
            end_line = source.find("\n", token.end)
            if end_line == -1:
                end_line = len(source)
            line = source[line_start:end_line]
            prev_line_start = source.rfind("\n", 0, max(0, line_start - 1)) + 1
            ignored_comment = any("NO_TRANSLATE" in c.text and
                                  prev_line_start <= c.start <= end_line for c in comments)
            next_token = tokens[index + 1] if index + 1 < len(tokens) else None
            statement = tokens[statement_start:index]
            words = [t.text for t in statement]
            calls = {name for _, name in stack}
            category, reason = "review", "Meaning is unknown; review the display/data flow manually."
            patchable = False
            if ignored_comment:
                category, reason = "ignored", "NO_TRANSLATE comment."
            elif previous and (previous.text in {"&", "^", "$", "%"} or
                               previous.text == "r" and previous.end == token.start):
                category, reason = "ignored", "StringName, NodePath, node lookup, or expression prefix."
            elif not any(c.isalpha() for c in body) or re.match(r"(?:[a-zA-Z]+://|[/\\])", body):
                category, reason = "ignored", "No alphabetic text or resource/absolute path."
            elif "const" in words or any(w in {"func", "signal", "@"} for w in words):
                category, reason = "ignored", "Constant, function/signal declaration, or annotation."
            elif next_token and next_token.text == ":":
                category, reason = "ignored", "Dictionary key or match-pattern-like syntax."
            elif any(w in {"==", "!=", "in", "<", ">", "<=", ">="} for w in words) or (
                    next_token and next_token.text in {"==", "!=", "in", "<", ">", "<=", ">="}):
                category, reason = "ignored", "Comparison or membership expression."
            elif calls & TRANSLATORS:
                category, reason = "translated", "Inside an existing Godot translation call."
            elif (previous and previous.text in {"=", ":="} and index >= 2 and
                  tokens[index - 2].text in BUILTIN_PROPERTIES) or calls & BUILTIN_METHODS:
                category, reason = "builtin", "Recognized Godot extraction pattern; use built-in POT extraction first."
            elif len(words) == 2 and words[0] in allowed and words[1] == "(" and next_token and next_token.text == ")":
                after = tokens[index + 2] if index + 2 < len(tokens) else None
                before_call = source[line_start:tokens[statement_start].start]
                whole_line = tokens[statement_start].start >= line_start and not before_call.lstrip("\ufeff").strip() and (
                    after is None or "\n" in source[next_token.end:after.start])
                unsafe_context = tool_script or any(a <= token.start < b for a, b in static_ranges)
                format_text = any(c in body for c in "%{}")
                if whole_line and not unsafe_context and not format_text and "\n" not in token.text and not token.text.startswith(('"""', "'''")):
                    category, reason = "candidate", "Single literal in an explicitly allowlisted standalone display call."
                    patchable = True
            findings.append({"path": str(path), "line": source.count("\n", 0, token.start) + 1,
                             "column": token.start - line_start + 1, "text": body,
                             "category": category, "reason": reason, "patchable": patchable,
                             "start": token.start, "end": token.end})
        if token.text in {"(", "[", "{"} and token.kind == "symbol":
            stack.append((token.text, previous.text if token.text == "(" and previous and previous.kind == "identifier" else ""))
        elif token.text in {")", "]", "}"} and token.kind == "symbol":
            if not stack or stack[-1][0] != {")": "(", "]": "[", "}": "{"}[token.text]:
                raise ValueError(f"unmatched bracket at offset {token.start}")
            stack.pop()
    if stack:
        raise ValueError("unclosed bracket; no patch can be proposed")
    return findings


def _is_link(path: Path) -> bool:
    # Windows directory junctions/reparse points are also excluded.
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)


def _sources(path: Path) -> list[Path]:
    if not path.exists():
        raise ValueError(f"path does not exist: {path}")
    if _is_link(path) or any(_is_link(parent) for parent in path.absolute().parents):
        raise ValueError("symlink/reparse-point input paths are not supported")
    if path.is_file():
        if path.suffix.lower() != ".gd":
            raise ValueError("scan expects a .gd file or a directory")
        return [path]
    found = []
    for base, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d.lower() not in SKIP_DIRS and not _is_link(Path(base) / d))
        for name in sorted(files):
            item = Path(base) / name
            if item.suffix.lower() == ".gd" and not _is_link(item):
                found.append(item)
                if len(found) > MAX_FILES:
                    raise ValueError(f"file count exceeds {MAX_FILES}")
    return found


def _read(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {MAX_FILE_BYTES} bytes")
    data = path.read_bytes()
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"file exceeds {MAX_FILE_BYTES} bytes")
    return data.decode("utf-8")  # Keep a BOM in diff context; never alter source bytes.


def scan_path(path: str | Path, display_functions: Iterable[str] = ()) -> dict:
    root = Path(path)
    report = {"version": "0.1.0", "root": str(root), "findings": [], "files_scanned": 0, "errors": []}
    try:
        allowed = _validate_functions(display_functions)
        files = _sources(root)
    except (OSError, ValueError) as exc:
        report["errors"].append({"path": str(root), "message": str(exc)})
        return report
    for item in files:
        relative = item.name if root.is_file() else item.relative_to(root).as_posix()
        try:
            report["findings"].extend(scan_source(_read(item), relative, allowed))
            report["files_scanned"] += 1
        except (OSError, ValueError) as exc:
            report["errors"].append({"path": relative, "message": str(exc)})
    return report


def proposed_patch(path: str | Path, display_functions: Iterable[str] = ()) -> str:
    """Return unified diff, never write files. Any input error blocks all output."""
    root = Path(path)
    allowed = _validate_functions(display_functions)
    report = scan_path(root, allowed)
    if report["errors"]:
        raise ValueError("; ".join(f"{e['path']}: {e['message']}" for e in report["errors"]))
    chunks = []
    for item in _sources(root):
        name = item.name if root.is_file() else item.relative_to(root).as_posix()
        source = _read(item)
        findings = scan_source(source, name, allowed)
        changed = source
        for finding in reversed(findings):
            if finding["patchable"]:
                a, b = finding["start"], finding["end"]
                changed = changed[:a] + "tr(" + changed[a:b] + ")" + changed[b:]
        if changed != source:
            # Git-style diff needs an explicit no-newline marker for EOF lines.
            diff = difflib.unified_diff(source.splitlines(keepends=True), changed.splitlines(keepends=True),
                                        fromfile=f"a/{name}", tofile=f"b/{name}")
            for line in diff:
                if line.endswith("\n"):
                    chunks.append(line)
                else:
                    chunks.append(line + "\n\\ No newline at end of file\n")
    return "".join(chunks)
