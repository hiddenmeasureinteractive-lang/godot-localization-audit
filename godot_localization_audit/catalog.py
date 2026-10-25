"""Checks for source-string-key Godot CSV catalogs, not opaque-ID catalogs."""
from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
import re
import string

from .scanner import MAX_FILE_BYTES, _is_link

PERCENT = re.compile(r"%[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[diouxXfFeEgGcs]")
BBCODE = re.compile(r"\[(/?)([A-Za-z][A-Za-z0-9_]*)(?:[ =][^\]]*)?\]")


def _percent_signature(text: str) -> tuple:
    result = []
    i = 0
    while i < len(text):
        if text.startswith("%%", i):
            i += 2
        elif text[i] == "%":
            match = PERCENT.match(text, i)
            if match:
                value = match.group()
                result.append((value[-1], value.count("*")))
                i = match.end()
            else:
                # A prose percentage is not a formatting operation.
                i += 1
        else:
            i += 1
    return tuple(result)


def _brace_signature(text: str) -> tuple:
    # Godot String.format uses named/indexed braces. Python's parser gives a
    # useful conservative syntax check, not a claim of full Godot conformance.
    result = []
    for _, field, spec, conversion in string.Formatter().parse(text):
        if field is not None:
            result.append((field, spec, conversion or ""))
    return tuple(sorted(result))


def _bbcode_signature(text: str) -> tuple:
    # Tag names/order are checked; tag attributes are not semantic validation.
    return tuple((m.group(1), m.group(2).lower()) for m in BBCODE.finditer(text))


def check_catalog(path: str | Path) -> dict:
    item = Path(path)
    report = {"path": str(item), "issues": [], "errors": [], "rows_checked": 0}
    try:
        if _is_link(item) or any(_is_link(p) for p in item.absolute().parents):
            raise ValueError("symlink/reparse-point catalogs are not supported")
        if item.stat().st_size > MAX_FILE_BYTES:
            raise ValueError(f"catalog exceeds {MAX_FILE_BYTES} bytes")
        data = item.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"catalog exceeds {MAX_FILE_BYTES} bytes")
        rows = list(csv.reader(StringIO(data.decode("utf-8-sig"), newline=""), strict=True))
        if not rows or len(rows[0]) < 2:
            raise ValueError("catalog needs a header and at least one locale column")
        header = rows[0]
        if header[0].strip().lower() not in {"keys", "key", "source", "id"}:
            raise ValueError("first header must be keys/key/source/id; rows must use source-string keys")
        locales = [value.strip() for value in header[1:]]
        if any(not v for v in locales) or len(set(locales)) != len(locales):
            raise ValueError("locale headers must be non-empty and unique")
        keys = set()
        for number, row in enumerate(rows[1:], 2):
            if not row or not any(row):
                continue
            if len(row) != len(header):
                raise ValueError(f"row {number}: expected {len(header)} columns, found {len(row)}")
            key = row[0]
            if not key:
                raise ValueError(f"row {number}: empty source key")
            if key in keys:
                raise ValueError(f"row {number}: duplicate source key")
            keys.add(key)
            report["rows_checked"] += 1
            for locale, translated in zip(locales, row[1:]):
                def issue(kind: str, message: str) -> None:
                    report["issues"].append({"row": number, "locale": locale, "key": key,
                                             "kind": kind, "message": message})
                if not translated:
                    issue("missing_translation", "Translation is empty.")
                    continue
                if _percent_signature(key) != _percent_signature(translated):
                    issue("percent_placeholders", "Percent placeholder types/order or dynamic width arguments differ.")
                try:
                    if _brace_signature(key) != _brace_signature(translated):
                        issue("brace_placeholders", "Named/indexed brace placeholders differ.")
                except ValueError:
                    issue("brace_syntax", "Unbalanced or unsupported brace syntax; review manually.")
                if _bbcode_signature(key) != _bbcode_signature(translated):
                    issue("bbcode", "BBCode tag names/order differ; attributes are not checked.")
    except (OSError, ValueError, csv.Error) as exc:
        report["errors"].append(str(exc))
    return report
