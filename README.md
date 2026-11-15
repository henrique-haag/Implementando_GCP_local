# Request/Reply sobre Google Cloud Pub/Sub

```
 PC A                                   Nuvem (Pub/Sub)                          PC B
┌──────────┐  publish   ┌───────────────┐  pull   ┌─────────────────┐
│ client.py│──────────▶ │ rpc-requests  │ ──────▶ │ worker.py (xN)  │
│          │            └───────────────┘         │ processa        │
│ t_send   │            ┌───────────────┐ publish │                 │
│ t_recv   │◀────────── │ rpc-replies   │ ◀────── │                 │
└──────────┘   pull     └───────────────┘         └─────────────────┘
                  rpc-requests-sub --(5 falhas)--> rpc-requests-dlq
```
Correlação: atributos `corr_id`, `run_id` e `seq` copiados da requisição para a resposta.

## 1. Preparação (uma vez, em cada PC)
```bash
pip install -r requirements.txt
gcloud auth application-default login
export GCP_PROJECT=<seu-projeto>        # em cada PC
```
No PC A (uma vez): `./batch_files/setup.sh 10`  (10 = ack deadline em segundos). Ao terminar: `./batch_files/teardown.sh`.

**Alerta de custo (uma vez, quem administra o billing):** `./batch_files/budget.sh 5USD`
(use a moeda da conta de faturamento, ex.: `25BRL`). Avisa por e-mail em 50/90/100% do valor —
**não bloqueia gastos**. O `teardown.sh` não remove o alerta.

## 2. Cenários (comandos)

| Cenário | PC B (workers) | PC A (`./batch_files/run_scenarios.sh ...`) |
|---|---|---|
| baseline | `python setup/worker.py --procs 1 --threads 4` | `baseline` |
| rate | idem | `rate` |
| payload | idem | `payload` |
| cost | `python setup/worker.py --procs 1 --threads 1` | `cost` |
| batch | idem baseline | `batch` |
| workers | `python setup/worker.py --procs K --threads 1` (K = 1, 2, 4, 8) | `workers K` |
| topology | K=1: tudo no PC A; K=2: workers no PC B | `topology 1` / `topology 2` |
| fault | terminal 1: `python setup/worker.py --procs 1 --threads 4`; terminal 2: `python setup/worker.py --procs 1 --threads 4 --crash-after 300` | `fault 10` (refazer com `./batch_files/setup.sh 30` e `fault 30`) |
| nack/DLQ | `python setup/worker.py --procs 2 --fail-rate 0.5` | `nack 0.5` |

Entre cenários, **reinicie os workers** com a configuração indicada.
Mensagens do DLQ: `gcloud pubsub subscriptions pull rpc-requests-dlq-sub --limit 10`.

## 3. Resultados
```bash
python setup/analyze.py results     # gera results/tabela.md, tabela.csv e os PNGs
```
