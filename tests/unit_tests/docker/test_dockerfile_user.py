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
Smoke tests verifying the Dockerfile runtime stages run as a non-root user.

Container user regressions are easy to miss in review but high-signal for
production hardening. These tests parse the Dockerfile statically — no image
build required — so they are fast enough for CI.

Expected runtime user: ``superset`` (UID created in the ``python-base`` stage).

Local quick-check::

    pytest tests/unit_tests/docker/test_dockerfile_user.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Stages that produce runnable images (have a CMD / ENTRYPOINT or are the final
# stage). Build-only stages (superset-node-ci, superset-node,
# python-translation-compiler, …) intentionally run as root during the build.
RUNTIME_STAGES: set[str] = {"lean", "dev", "ci", "showtime"}
EXPECTED_USER: str = "superset"

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = REPO_ROOT / "Dockerfile"


def _parse_stage_users(dockerfile: Path) -> dict[str, str | None]:
    """Return ``{stage_name: last_USER_value}`` for every stage in *dockerfile*.

    If a stage never issues a ``USER`` instruction the value is ``None``.
    """
    stage_re = re.compile(r"^\s*FROM\s+\S+\s+AS\s+(\S+)", re.IGNORECASE)
    user_re = re.compile(r"^\s*USER\s+(\S+)", re.IGNORECASE)

    stages: dict[str, str | None] = {}
    current_stage: str | None = None

    for line in dockerfile.read_text().splitlines():
        if match := stage_re.search(line):
            current_stage = match.group(1)
            stages[current_stage] = None
        elif current_stage and (match := user_re.match(line)):
            stages[current_stage] = match.group(1)

    return stages


@pytest.fixture(scope="module")
def stage_users() -> dict[str, str | None]:
    if not DOCKERFILE.is_file():
        pytest.skip("Dockerfile not found at repo root")
    return _parse_stage_users(DOCKERFILE)


@pytest.mark.parametrize("stage", sorted(RUNTIME_STAGES))
def test_runtime_stage_runs_as_non_root(
    stage: str, stage_users: dict[str, str | None]
) -> None:
    """Each runtime stage must set USER to a non-root identity."""
    if stage not in stage_users:
        pytest.fail(
            f"Stage '{stage}' not found in Dockerfile — was it renamed or removed?"
        )
    user = stage_users[stage]
    assert user is not None, (
        f"Stage '{stage}' never sets USER — container would run as root"
    )
    assert user not in ("root", "0"), (
        f"Stage '{stage}' sets USER to '{user}' — container must not run as root"
    )


def test_runtime_stages_use_expected_user(
    stage_users: dict[str, str | None],
) -> None:
    """All runtime stages should converge on the same dedicated user."""
    for stage in sorted(RUNTIME_STAGES):
        if stage not in stage_users:
            continue
        user = stage_users[stage]
        assert user == EXPECTED_USER, (
            f"Stage '{stage}' runs as '{user}', expected '{EXPECTED_USER}'"
        )
