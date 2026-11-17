#!/usr/bin/env bash
# Remove as 4 assinaturas e os 3 topicos criados pelo setup.sh.
# Uso: bash scripts/teardown.sh [-y]   (-y pula a confirmacao)
set -euo pipefail

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "-y" ) ]]; then
    echo "Uso: bash $(basename "$0") [-y]" >&2
    exit 1
fi

: "${GCP_PROJECT:?Defina GCP_PROJECT (ex.: export GCP_PROJECT=teste-pub-sub-515002)}"

if ! command -v gcloud >/dev/null 2>&1; then
    echo "Erro: gcloud nao encontrado no PATH." >&2
    exit 1
fi

TOPICOS=(ambiente gases eventos)
ASSINATURAS=(sub-b-ambiente sub-c-gases sub-d-gases sub-d-eventos)

if [[ "${1:-}" != "-y" ]]; then
    read -r -p "Remover ${#ASSINATURAS[@]} assinaturas e ${#TOPICOS[@]} topicos do projeto $GCP_PROJECT? [s/N] " resp
    [[ "$resp" =~ ^[sS]$ ]] || { echo "Cancelado."; exit 0; }
fi

# Assinaturas primeiro (dependem dos topicos)
for sub in "${ASSINATURAS[@]}"; do
    if gcloud pubsub subscriptions describe "$sub" --project="$GCP_PROJECT" >/dev/null 2>&1; then
        gcloud pubsub subscriptions delete "$sub" --project="$GCP_PROJECT" --quiet
    else
        echo "Assinatura nao existe: $sub"
    fi
done

for t in "${TOPICOS[@]}"; do
    if gcloud pubsub topics describe "$t" --project="$GCP_PROJECT" >/dev/null 2>&1; then
        gcloud pubsub topics delete "$t" --project="$GCP_PROJECT" --quiet
    else
        echo "Topico nao existe: $t"
    fi
done

echo "Teardown concluido."
