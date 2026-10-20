#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
    printf 'Run bash setup.sh first.\n' >&2
    exit 1
fi
.venv/bin/python main.py --check
.venv/bin/python -m unittest discover -v
printf '\nA full run must have no failures, errors or skipped tests.\n'
printf 'Then follow docs/ACCEPTANCE_CHECKLIST.md for visual and hardware checks.\n'
