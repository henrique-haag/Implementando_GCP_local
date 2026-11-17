#!/usr/bin/env bash
# Cria os 3 topicos e as 4 assinaturas do prototipo (idempotente).
# Uso: bash scripts/setup.sh
# Os nomes abaixo repetem os de src/common.py: manter os dois em sincronia.
set -euo pipefail

if [[ $# -gt 0 ]]; then
    echo "Uso: bash $(basename "$0")   (sem argumentos; projeto lido de GCP_PROJECT)" >&2
    exit 1
fi

: "${GCP_PROJECT:?Defina GCP_PROJECT (ex.: export GCP_PROJECT=teste-pub-sub-515002)}"

if ! command -v gcloud >/dev/null 2>&1; then
    echo "Erro: gcloud nao encontrado no PATH." >&2
    exit 1
fi

TOPICOS=(ambiente gases eventos)
# assinatura:topico
ASSINATURAS=(
    "sub-b-ambiente:ambiente"
    "sub-c-gases:gases"
    "sub-d-gases:gases"
    "sub-d-eventos:eventos"
)
ACK_DEADLINE=60

echo "Projeto: $GCP_PROJECT"
gcloud services enable pubsub.googleapis.com --project="$GCP_PROJECT"

for t in "${TOPICOS[@]}"; do
    if gcloud pubsub topics describe "$t" --project="$GCP_PROJECT" >/dev/null 2>&1; then
        echo "Topico ja existe: $t"
    else
        gcloud pubsub topics create "$t" --project="$GCP_PROJECT"
    fi
done

for par in "${ASSINATURAS[@]}"; do
    sub="${par%%:*}"
    topico="${par##*:}"
    if gcloud pubsub subscriptions describe "$sub" --project="$GCP_PROJECT" >/dev/null 2>&1; then
        echo "Assinatura ja existe: $sub"
    else
        gcloud pubsub subscriptions create "$sub" \
            --project="$GCP_PROJECT" \
            --topic="$topico" \
            --ack-deadline="$ACK_DEADLINE"
    fi
done

echo
echo "Estado final:"
gcloud pubsub topics list --project="$GCP_PROJECT" --format="value(name)"
gcloud pubsub subscriptions list --project="$GCP_PROJECT" --format="table(name.basename(),topic.basename(),ackDeadlineSeconds)"
