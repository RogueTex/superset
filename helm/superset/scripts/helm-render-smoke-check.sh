#!/usr/bin/env bash
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# Helm render smoke check for the Superset chart.
#
# Renders the chart with `helm template` and verifies:
#   1. Dependency-wait init containers are present in the rendered output.
#   2. The dedicated `apache/superset:dockerize` helper image is NOT used.
#
# Usage:
#   ./helm/superset/scripts/helm-render-smoke-check.sh [CHART_DIR]
#
# CHART_DIR defaults to ./helm/superset when omitted.
#
# Exit codes:
#   0  All checks passed.
#   1  One or more checks failed.
#   2  Helm template rendering failed.

set -euo pipefail

CHART_DIR="${1:-./helm/superset}"
RENDERED=$(mktemp)
trap 'rm -f "$RENDERED"' EXIT

echo "==> Rendering chart from ${CHART_DIR} ..."
if ! helm template superset "$CHART_DIR" > "$RENDERED" 2>&1; then
  echo "FAIL: helm template failed:"
  cat "$RENDERED"
  exit 2
fi

PASS=true

# --- Check 1: init containers exist -------------------------------------------
echo "==> Checking for dependency-wait init containers ..."
INIT_COUNT=$(grep -c 'name: wait-for-' "$RENDERED" || true)
if [ "$INIT_COUNT" -eq 0 ]; then
  echo "FAIL: No dependency-wait init containers (name: wait-for-*) found."
  PASS=false
else
  echo "OK:   Found ${INIT_COUNT} dependency-wait init container(s)."
fi

# --- Check 2: no apache/superset:dockerize image ------------------------------
echo "==> Checking for apache/superset:dockerize image references ..."
DOCKERIZE_LINES=$(grep -n 'apache/superset:dockerize' "$RENDERED" || true)
if [ -n "$DOCKERIZE_LINES" ]; then
  echo "FAIL: Rendered chart references the dedicated dockerize helper image."
  echo "      Matching lines:"
  echo "$DOCKERIZE_LINES" | sed 's/^/        /'
  echo ""
  echo "      The 'apache/superset:dockerize' image is a supply-chain concern."
  echo "      Prefer using the main Superset image or a minimal busybox-based"
  echo "      wait loop instead."
  PASS=false
else
  echo "OK:   No apache/superset:dockerize image references found."
fi

# --- Summary -------------------------------------------------------------------
echo ""
if [ "$PASS" = true ]; then
  echo "All smoke checks passed."
  exit 0
else
  echo "One or more smoke checks failed."
  exit 1
fi
