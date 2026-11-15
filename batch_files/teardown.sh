#!/usr/bin/env bash
# Remove tudo (para nao deixar recursos no projeto).
# Uso: GCP_PROJECT=meu-projeto ./batch_files/teardown.sh
P=${GCP_PROJECT:?defina GCP_PROJECT}
for s in rpc-requests-sub rpc-replies-sub rpc-requests-dlq-sub; do
  gcloud pubsub subscriptions delete $s --project "$P" --quiet
done
for t in rpc-requests rpc-replies rpc-requests-dlq; do
  gcloud pubsub topics delete $t --project "$P" --quiet
done
