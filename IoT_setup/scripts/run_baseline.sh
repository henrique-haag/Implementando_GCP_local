#!/usr/bin/env bash
# Cenario baseline: 10 msgs/s (total), 70 s, 3 repeticoes.
# Uso: bash scripts/run_baseline.sh <pc-a|pc-b|pc-c|pc-d> <run_id>
# Ordem: iniciar em B, C e D primeiro; depois em A, com o mesmo run_id.
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Uso: bash $(basename "$0") <pc-a|pc-b|pc-c|pc-d> <run_id>" >&2
    exit 1
fi
exec bash "$(dirname "${BASH_SOURCE[0]}")/run_cenario.sh" baseline 10 "$1" "$2"
