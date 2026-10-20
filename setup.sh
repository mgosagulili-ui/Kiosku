#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
    "${PYTHON:-python3}" -m venv .venv
fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py --check
printf '\nSetup finished. Start with: bash run.sh\n'
