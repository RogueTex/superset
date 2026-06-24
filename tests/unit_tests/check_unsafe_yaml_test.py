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

from __future__ import annotations

import importlib.util
import textwrap
from pathlib import Path
from types import ModuleType

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "scripts" / "check_unsafe_yaml.py"
)


def _load_checker() -> ModuleType:
    """Import the check script as a module without running ``__main__``."""
    spec = importlib.util.spec_from_file_location("check_unsafe_yaml", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


checker = _load_checker()


def _write(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(textwrap.dedent(content))
    return f


def test_safe_load_is_allowed(tmp_path: Path) -> None:
    f = _write(tmp_path, "import yaml\ndata = yaml.safe_load(stream)\n")
    assert checker.scan_file(f) == []


def test_safe_loader_kwarg_is_allowed(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "import yaml\ndata = yaml.load(stream, Loader=yaml.SafeLoader)\n",
    )
    assert checker.scan_file(f) == []


def test_csafe_loader_kwarg_is_allowed(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "import yaml\ndata = yaml.load(stream, Loader=yaml.CSafeLoader)\n",
    )
    assert checker.scan_file(f) == []


def test_suppression_comment_is_allowed(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        (
            "import yaml\n"
            "data = yaml.load(stream, Loader=yaml.Loader)"
            "  # yaml-load-safe\n"
        ),
    )
    assert checker.scan_file(f) == []


def test_bare_yaml_load_is_flagged(tmp_path: Path) -> None:
    f = _write(tmp_path, "import yaml\ndata = yaml.load(stream)\n")
    violations = checker.scan_file(f)
    assert len(violations) == 1
    assert violations[0][0] == 2


def test_yaml_load_with_full_loader_is_flagged(tmp_path: Path) -> None:
    f = _write(
        tmp_path,
        "import yaml\ndata = yaml.load(stream, Loader=yaml.Loader)\n",
    )
    violations = checker.scan_file(f)
    assert len(violations) == 1


def test_main_returns_zero_on_clean_files(tmp_path: Path) -> None:
    f = _write(tmp_path, "import yaml\ndata = yaml.safe_load(stream)\n")
    assert checker.main([str(f)]) == 0


def test_main_returns_one_on_violations(tmp_path: Path) -> None:
    f = _write(tmp_path, "import yaml\ndata = yaml.load(stream)\n")
    assert checker.main([str(f)]) == 1
