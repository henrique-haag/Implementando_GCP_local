#!/usr/bin/env bash
# Cria topicos, subscriptions e dead letter topic. Rodar uma vez.
# Uso: GCP_PROJECT=meu-projeto ./setup.sh [ACK_DEADLINE_SEGUNDOS]
set -euo pipefail
P=${GCP_PROJECT:?defina GCP_PROJECT}
ACK=${1:-10}

gcloud config set project "$P"
gcloud services enable pubsub.googleapis.com

gcloud pubsub topics create rpc-requests
gcloud pubsub topics create rpc-replies
gcloud pubsub topics create rpc-requests-dlq
gcloud pubsub subscriptions create rpc-requests-dlq-sub --topic rpc-requests-dlq

gcloud pubsub subscriptions create rpc-requests-sub --topic rpc-requests \
  --ack-deadline="$ACK" \
  --dead-letter-topic=rpc-requests-dlq --max-delivery-attempts=5
gcloud pubsub subscriptions create rpc-replies-sub --topic rpc-replies \
  --ack-deadline=10

# Permissoes para o Pub/Sub encaminhar mensagens ao dead letter topic
PN=$(gcloud projects describe "$P" --format='value(projectNumber)')
SA="serviceAccount:service-${PN}@gcp-sa-pubsub.iam.gserviceaccount.com"
gcloud pubsub topics add-iam-policy-binding rpc-requests-dlq \
  --member="$SA" --role=roles/pubsub.publisher
gcloud pubsub subscriptions add-iam-policy-binding rpc-requests-sub \
  --member="$SA" --role=roles/pubsub.subscriber

echo "Pronto. Ack deadline da subscription de requisicoes: ${ACK}s"
