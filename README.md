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
No PC A (uma vez): `./setup.sh 10`  (10 = ack deadline em segundos). Ao terminar: `./teardown.sh`.

## 2. Cenários (comandos)

| Cenário | PC B (workers) | PC A (`./run_scenarios.sh ...`) |
|---|---|---|
| baseline | `python worker.py --procs 1 --threads 4` | `baseline` |
| rate | idem | `rate` |
| payload | idem | `payload` |
| cost | `python worker.py --procs 1 --threads 1` | `cost` |
| batch | idem baseline | `batch` |
| workers | `python worker.py --procs K --threads 1` (K = 1, 2, 4, 8) | `workers K` |
| topology | K=1: tudo no PC A; K=2: workers no PC B | `topology 1` / `topology 2` |
| fault | terminal 1: `python worker.py --procs 1 --threads 4`; terminal 2: `python worker.py --procs 1 --threads 4 --crash-after 300` | `fault 10` (refazer com `./setup.sh 30` e `fault 30`) |
| nack/DLQ | `python worker.py --procs 2 --fail-rate 0.5` | `nack 0.5` |

Entre cenários, **reinicie os workers** com a configuração indicada.
Mensagens do DLQ: `gcloud pubsub subscriptions pull rpc-requests-dlq-sub --limit 10`.

## 3. Resultados
```bash
python analyze.py results     # gera results/tabela.md, tabela.csv e os PNGs
```
