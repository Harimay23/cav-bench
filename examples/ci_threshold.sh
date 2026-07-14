#!/usr/bin/env bash
# Example CI regression gate: fail the build if CVSR drops below a
# threshold for a given profile. Replace --profile with a custom adapter
# integration once you have one (see docs/adapter-authoring.md); the CLI
# itself only knows the five built-in baseline names.
#
# Usage: examples/ci_threshold.sh [profile] [threshold]
set -euo pipefail

PROFILE="${1:-full_lifecycle}"
THRESHOLD="${2:-0.95}"

set +e
cavbench run --profile "${PROFILE}" --seed 0 --output runs/ci --fail-on-cvsr-below "${THRESHOLD}"
STATUS=$?
set -e

if [ "${STATUS}" -eq 2 ]; then
  echo "CAV-Bench regression gate FAILED: CVSR below ${THRESHOLD} for profile ${PROFILE}" >&2
  exit 1
elif [ "${STATUS}" -ne 0 ]; then
  echo "CAV-Bench run failed to execute (exit ${STATUS})" >&2
  exit "${STATUS}"
fi

echo "CAV-Bench regression gate passed for profile ${PROFILE} (CVSR >= ${THRESHOLD})"
