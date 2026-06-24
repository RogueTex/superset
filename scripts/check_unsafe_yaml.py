#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""
Guard against unsafe YAML deserialization.

Scans Python files for ``yaml.load()`` calls that do not explicitly use
``SafeLoader`` or ``CSafeLoader``.  Calls to ``yaml.safe_load()`` are
fine and are not flagged.

Suppress a finding with an inline ``# yaml-load-safe`` comment on the
same line as the call.

Usage:
    python scripts/check_unsafe_yaml.py [paths ...]

If no paths are given the script scans ``superset/`` and ``scripts/``.

Exit codes:
    0  No unsafe calls found.
    1  One or more unsafe calls detected.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

SAFE_LOADERS = {"SafeLoader", "CSafeLoader"}
SUPPRESSION = "yaml-load-safe"


def _loader_is_safe(call: ast.Call) -> bool:
    """Return True if the ``Loader=`` keyword uses a safe loader class."""
    for kw in call.keywords:
        if kw.arg == "Loader" and isinstance(kw.value, ast.Attribute):
            if kw.value.attr in SAFE_LOADERS:
                return True
    return False


def _line_suppressed(source_lines: list[str], lineno: int) -> bool:
    """Return True if the source line has a ``# yaml-load-safe`` comment."""
    if 0 < lineno <= len(source_lines):
        return SUPPRESSION in source_lines[lineno - 1]
    return False


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, line_text)`` pairs for unsafe ``yaml.load()`` calls."""
    try:
        source = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []

    source_lines = source.splitlines()
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        # Match ``yaml.load(...)``
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "load"
            and isinstance(func.value, ast.Name)
            and func.value.id == "yaml"
        ):
            lineno = node.lineno
            if _loader_is_safe(node):
                continue
            if _line_suppressed(source_lines, lineno):
                continue
            line_text = (
                source_lines[lineno - 1].strip() if lineno <= len(source_lines) else ""
            )
            violations.append((lineno, line_text))

    return violations


def scan_paths(paths: list[Path]) -> dict[Path, list[tuple[int, str]]]:
    """Scan *paths* (files or directories) and return all violations."""
    results: dict[Path, list[tuple[int, str]]] = {}
    for path in paths:
        targets = path.rglob("*.py") if path.is_dir() else [path]
        for py_file in targets:
            if py_file.suffix != ".py":
                continue
            violations = scan_file(py_file)
            if violations:
                results[py_file] = violations
    return results


def main(argv: list[str] | None = None) -> int:
    """Entry point.  Returns 0 on success, 1 when violations are found."""
    args = argv if argv is not None else sys.argv[1:]
    if args:
        paths = [Path(a) for a in args]
    else:
        repo_root = Path(__file__).resolve().parent.parent
        paths = [repo_root / "superset", repo_root / "scripts"]

    results = scan_paths(paths)
    if not results:
        print("No unsafe yaml.load() calls found.")
        return 0

    print("Unsafe yaml.load() calls detected:\n")
    for filepath, violations in sorted(results.items()):
        for lineno, line in violations:
            print(f"  {filepath}:{lineno}: {line}")
    print(
        "\nUse yaml.safe_load() or pass Loader=yaml.SafeLoader / "
        "yaml.CSafeLoader.\n"
        "To suppress a false positive, add an inline # yaml-load-safe comment."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
