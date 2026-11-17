#!/usr/bin/env bash
# Cria um alerta de orcamento para o projeto. Rodar uma vez.
# ATENCAO: o alerta so AVISA por e-mail (50%, 90%, 100% e previsao de 100%); NAO bloqueia gastos.
# Precisa de permissao de Billing Account Administrator (ou Costs Manager) na conta de faturamento.
# A moeda deve ser a mesma da conta de faturamento (ex.: 5USD ou 25BRL).
# Uso: GCP_PROJECT=meu-projeto ./batch_files/budget.sh [VALOR_COM_MOEDA]
set -euo pipefail
P=${GCP_PROJECT:?defina GCP_PROJECT}
VALOR=${1:-5USD}

BA=$(gcloud billing projects describe "$P" --format='value(billingAccountName)')
BA=${BA#billingAccounts/}
if [ -z "$BA" ]; then
  echo "Projeto $P nao tem conta de faturamento vinculada (sem billing, nao ha cobranca)."
  exit 1
fi

gcloud services enable billingbudgets.googleapis.com --project "$P"

gcloud billing budgets create \
  --billing-project="$P" \
  --billing-account="$BA" \
  --display-name="rpc-pubsub-$P" \
  --budget-amount="$VALOR" \
  --filter-projects="projects/$P" \
  --threshold-rule=percent=0.5 \
  --threshold-rule=percent=0.9 \
  --threshold-rule=percent=1.0 \
  --threshold-rule=percent=1.0,basis=forecasted-spend

echo "Alerta criado: $VALOR no projeto $P (conta $BA). Avisos vao para os admins da conta de faturamento."
echo "Conferir: gcloud billing budgets list --billing-account=$BA"
