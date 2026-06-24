#!/usr/bin/env bash

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

# ---------------------------------------------------------------------------
# Smoke check: verify Dockerfile runtime stages run as the "superset" user.
#
# Usage:
#   scripts/check_docker_user.sh            # from repo root
#   scripts/check_docker_user.sh Dockerfile # explicit path
#
# Expected runtime user: superset
# Runtime stages checked: lean, dev, ci, showtime
# ---------------------------------------------------------------------------

set -euo pipefail

DOCKERFILE="${1:-Dockerfile}"
EXPECTED_USER="superset"
RUNTIME_STAGES="lean dev ci showtime"

if [[ ! -f "$DOCKERFILE" ]]; then
    echo "ERROR: $DOCKERFILE not found" >&2
    exit 1
fi

errors=0

for stage in $RUNTIME_STAGES; do
    # Extract the last USER instruction within the stage block.
    # A stage block starts with "FROM ... AS <stage>" and ends at the next
    # "FROM" or EOF.
    last_user=$(
        awk -v stage="$stage" '
            BEGIN { IGNORECASE=1; in_stage=0 }
            /^[[:space:]]*FROM/ {
                if (in_stage) exit
                if ($0 ~ "AS[[:space:]]+" stage "([[:space:]]|$)") in_stage=1
                next
            }
            in_stage && /^[[:space:]]*USER[[:space:]]+/ {
                gsub(/^[[:space:]]*USER[[:space:]]+/, "")
                gsub(/[[:space:]]+$/, "")
                user=$0
            }
            END { if (user) print user }
        ' "$DOCKERFILE"
    )

    if [[ -z "$last_user" ]]; then
        echo "FAIL: stage '$stage' never sets USER — would run as root"
        errors=$((errors + 1))
    elif [[ "$last_user" == "root" || "$last_user" == "0" ]]; then
        echo "FAIL: stage '$stage' sets USER to '$last_user'"
        errors=$((errors + 1))
    elif [[ "$last_user" != "$EXPECTED_USER" ]]; then
        echo "WARN: stage '$stage' runs as '$last_user', expected '$EXPECTED_USER'"
    else
        echo "OK:   stage '$stage' → USER $last_user"
    fi
done

if [[ $errors -gt 0 ]]; then
    echo ""
    echo "$errors runtime stage(s) would run as root — failing."
    exit 1
fi

echo ""
echo "All runtime stages run as non-root user '$EXPECTED_USER'."
