# Implementando Google Cloud Pub/Sub

Trabalho de faculdade (Grau B, em grupo): protótipos de comunicação via **Google Cloud Pub/Sub**
para medir latência, vazão, perdas e comportamento sob falha. Entregas: apresentação (aula 16) e
artigo em LaTeX no modelo SBC.

O repositório tem duas partes independentes, cada uma com scripts, dependências e resultados
próprios:

| Parte | Pasta | Padrão | O que mede |
|---|---|---|---|
| 1 | [`test_setup/`](test_setup/) | **Request/Reply** (PC A ⇄ PC B) | RTT, vazão, escalabilidade com workers, falha e DLQ |
| 2 | [`IoT_setup/`](IoT_setup/) | **Publish/Subscribe com fan-out** (PC A → PCs B, C, D) | latência ponta a ponta por assinatura, perdas, duplicatas, efeito da rede |

## Parte 1: Request/Reply ([`test_setup/`](test_setup/))

```
PC A: client.py ──▶ rpc-requests ──▶ worker.py (xN) :PC B
      (mede RTT) ◀── rpc-replies  ◀──     (processa)
```

- O client publica requisições a uma taxa constante. Os workers concorrem na mesma assinatura
  (competing consumers) e devolvem a resposta.
- O RTT é medido só com o relógio do PC A, então não é preciso sincronizar os relógios.
- Cenários: `baseline`, `rate`, `payload`, `cost`, `batch`, `workers`, `topology`, `fault` e `nack`.
- Passo a passo e comandos de cada cenário: [`test_setup/README.md`](test_setup/README.md).

## Parte 2: IoT com fan-out ([`IoT_setup/`](IoT_setup/))

| Tópico | Leituras | Assinaturas (uma por PC) |
|---|---|---|
| `ambiente` | temp, humidity | `sub-b-ambiente` (PC B) |
| `gases` | co, lpg, smoke | `sub-c-gases` (PC C), `sub-d-gases` (PC D) |
| `eventos` | motion, light | `sub-d-eventos` (PC D) |

- O PC A faz o replay do dataset [Environmental Sensor Telemetry](https://www.kaggle.com/datasets/garystafford/environmental-sensor-data-132k)
  (`iot_telemetry_data.csv`). Cada linha vira 3 mensagens, uma por tópico.
- A latência compara relógios de máquinas diferentes. Por isso, todos os PCs sincronizam o relógio
  com `time.google.com`, e o offset de cada um é registrado em `meta-<pc>.txt` a cada repetição.
- Cenários: `baseline` (10 msgs/s) e `happy_path` (20 msgs/s), com 70 s, 10 s de warm-up e 3 repetições.
- Arquitetura: [`IoT_setup/docs/`](IoT_setup/docs/). Convenções e limitações: [`IoT_setup/CLAUDE.md`](IoT_setup/CLAUDE.md).

```bash
export GCP_PROJECT=<projeto>
pip install -r IoT_setup/requirements.txt
# baixar iot_telemetry_data.csv do Kaggle para IoT_setup/dataset/ (não versionado)
bash IoT_setup/scripts/setup.sh                          # uma vez
bash IoT_setup/scripts/run_baseline.sh pc-b <run_id>     # primeiro em B, C e D; por último em pc-a
python IoT_setup/src/analyzer.py IoT_setup/dados         # tabelas e gráficos em IoT_setup/resultados/
bash IoT_setup/scripts/teardown.sh                       # ao terminar
```

## Pré-requisitos (nas duas partes)

- Python 3.10+, com um venv por parte.
- Google Cloud CLI (`gcloud`), que não vem pelo pip: `winget install Google.CloudSDK` no Windows,
  ou o instalador em cloud.google.com/sdk/docs/install.
- Autenticação em cada PC:
  ```bash
  gcloud init                              # login do gcloud (usado pelos .sh)
  gcloud auth application-default login    # credencial da biblioteca Python
  ```
- No Windows, os `.sh` rodam no Git Bash (ou WSL).

## Custos

As duas partes usam o **Pub/Sub real** (não o emulador). Pelo volume dos cenários, o uso deve ficar
dentro da faixa gratuita mensal. Mesmo assim:

- rode o `teardown.sh` da parte usada ao terminar;
- crie um alerta de orçamento com [`test_setup/batch_files/budget.sh`](test_setup/batch_files/budget.sh).
  O alerta só avisa por e-mail; ele não bloqueia gastos.
