# CLAUDE.md — IoT_setup

Trabalho de faculdade (Grau B, em grupo): protótipo **Pub/Sub com fan-out sobre Google Cloud Pub/Sub**,
com dados de sensores IoT. Entregas: apresentação (aula 16) e artigo em LaTeX no modelo SBC (até a prova do GB).
Doc de arquitetura (fonte da verdade): https://claude.ai/artifact/7LUh4QorHajahE9H8pCHQ9

Tudo desta parte vive em `IoT_setup/`. O resto do repo (parte 1, Request/Reply) não deve ser alterado.

## Arquitetura
- **PC A** publica o dataset em 3 tópicos. **PCs B, C e D** consomem só das suas assinaturas.
- Cada PC tem a sua própria assinatura (fan-out). **Nunca** compartilhar assinatura entre PCs:
  isso viraria competing consumers.

| Tópico | Leituras | Assinaturas |
|---|---|---|
| `ambiente` | temp, humidity | `sub-b-ambiente` (PC B) |
| `gases` | co, lpg, smoke | `sub-c-gases` (PC C), `sub-d-gases` (PC D) |
| `eventos` | motion, light | `sub-d-eventos` (PC D) |

- **Projeto GCP:** `teste-pub-sub-515002`, lido da variável de ambiente `GCP_PROJECT`.
- **Conta:** uma única conta Google em todos os PCs (fator do ambiente de teste).

## Máquinas
| PC | Papel | SO | Rede |
|---|---|---|---|
| A | produtor | Windows 11 (bashes no Git Bash) | Wi-Fi 5 GHz |
| B | `sub-b-ambiente` | VM Linux Mint dentro do PC A (VirtualBox, NAT) | via Wi-Fi 5 GHz do A |
| C | `sub-c-gases` | Linux Mint bare metal | Wi-Fi 2,4 GHz |
| D | `sub-d-gases` + `sub-d-eventos` | CachyOS bare metal (shell fish) | Wi-Fi 5 GHz |

Os scripts precisam rodar em **Windows (Git Bash) e Linux**: nada de comandos exclusivos de um SO
sem checagem (`uname`), e caminhos sempre relativos à raiz de `IoT_setup/`.

## Estrutura
```
IoT_setup/
├── requirements.txt         # google-cloud-pubsub, pandas, matplotlib (sem versão fixa)
├── scripts/
│   ├── setup.sh             # cria os 3 tópicos e as 4 assinaturas (gcloud)
│   ├── teardown.sh          # remove tudo o que o setup criou
│   ├── run_baseline.sh      # uso: run_baseline.sh <pc-a|pc-b|pc-c|pc-d> <run_id>
│   ├── run_happy_path.sh    # idem
│   └── run_cenario.sh       # logica comum dos dois run_* (repeticoes, seek, meta, logs)
├── src/
│   ├── common.py            # nomes, formato da mensagem, CSV, timestamp
│   ├── producer_pc_a.py
│   ├── consumer_pc_b.py     # sub-b-ambiente
│   ├── consumer_pc_c.py     # sub-c-gases
│   ├── consumer_pc_d.py     # sub-d-gases + sub-d-eventos (dois streaming pulls no mesmo processo)
│   └── analyzer.py
├── dataset/                 # iot_telemetry_data.csv do Kaggle (no .gitignore)
├── dados/<cenario>/<run_id>/rep<N>/   # pc-a.csv, pc-b.csv, pc-c.csv, pc-d.csv, meta-<pc>.txt
└── resultados/              # tabelas e gráficos do analyzer
```

## Dados
- **Dataset:** Environmental Sensor Telemetry (Kaggle, garystafford), arquivo `iot_telemetry_data.csv`.
  Colunas esperadas: `ts, device, co, humidity, light, lpg, motion, smoke, temp` (conferir no arquivo).
- Cada linha do dataset gera **3 mensagens**, uma por tópico, com o mesmo `ts_evento`.
- O produtor lê o CSV com o módulo `csv` padrão (sem pandas) e faz o replay em loop se o arquivo acabar.

## Mensagem
- **Payload (JSON):** `run_id`, `seq`, `device_id`, `ts_evento`, `ts_publicacao` + as leituras do tópico.
- **Atributos do Pub/Sub:** `run_id`, `device_id`, `tipo` (nome do tópico).
- `seq`: inteiro único por rodada, global entre os 3 tópicos (chave para perdas e duplicatas).
- **Timestamps:** `time.time()` em epoch, em milissegundos (float). Aqui é **obrigatório** usar o relógio
  de parede, porque a latência compara máquinas diferentes. Não usar `perf_counter` para timestamps.

## CSVs (colunas iguais em todos os PCs; escritos pelo `common.py`)
- **pc-a.csv:** `run_id, cenario, rep, topico, device_id, seq, ts_evento, ts_publicacao, message_id`
- **pc-b/c/d.csv:** `run_id, cenario, rep, pc, assinatura, topico, device_id, seq, message_id,
  ts_publicacao, publish_time_servidor, ts_recebimento`
  (`publish_time_servidor` = `message.publish_time` do Pub/Sub, permite separar A→nuvem de nuvem→PC)
- **meta-<pc>.txt:** hostname, SO, versão do Python, `pip freeze` e o offset do relógio no início e no fim da rodada.

## Consumidores
- Streaming pull, **ack manual depois de gravar a linha no CSV** (at-least-once: duplicatas são contadas,
  não evitadas).
- Encerram sozinhos após `--idle-timeout` segundos sem mensagens (padrão 15 s).
- Ignoram (mas contam no log) mensagens com `run_id` diferente do atual.

## Cenários
| Cenário | Taxa (msgs/s publicadas, total) | Duração | Warm-up descartado | Repetições |
|---|---|---|---|---|
| baseline | 10 | 70 s | 10 s iniciais | 3 |
| happy path | 20 | 70 s | 10 s iniciais | 3 |

- O gerador é de taxa constante (open loop). Registrar a taxa real alcançada.
- Ordem: iniciar os consumidores B, C e D, depois o produtor A, com o mesmo `run_id`.
- Antes de cada repetição, o run script do PC A faz `gcloud pubsub subscriptions seek <sub> --time=<agora>`
  nas 4 assinaturas, para descartar sobras.
- Com o fan-out, `gases` entrega cada mensagem duas vezes (C e D).

## Analyzer
Junta os CSVs por `(run_id, rep, seq)` e calcula, **por PC e por assinatura**:
- latência = `ts_recebimento − ts_publicacao`: média, p50, p95, p99 (média ± desvio entre as repetições);
- vazão recebida (msgs/s);
- perdas = publicadas no tópico e não recebidas pela assinatura;
- duplicatas = mesmo `seq` recebido mais de uma vez na mesma assinatura.
Gera `resultados/tabela.md`, `tabela.csv` e gráficos (CDF de latência por assinatura, latência ao longo
do tempo, comparação C × D no tópico `gases`).

## Decisões (não alterar sem discutir)
- GCP real, não o emulador.
- Uma assinatura por PC; o PC D roda as duas assinaturas num só processo.
- Um script Python por PC; tudo o que é comum fica no `common.py`.
- O PC A também grava CSV (referência para perdas).
- Configuração por `GCP_PROJECT` + nomes fixos no `common.py` (também repetidos no `setup.sh`). Sem `.env`.
- Um só `requirements.txt`, últimas versões, sem fixar.
- Venvs ficam fora do repo (`~/venvs/iot`); os bashes **supõem o venv já ativado** e devem checar no início
  se `google.cloud.pubsub` importa, com uma mensagem clara se não.
- Relógios sincronizados com `time.google.com` (chrony nos Linux, `w32time` no Windows). O offset é
  registrado; ele não é corrigido nos dados, mas entra nas limitações.

## Offset do relógio (nos run scripts)
- Linux: `chronyc tracking` (linha *System time*).
- Windows (Git Bash, `uname` começa com `MINGW`): `w32tm //stripchart //computer:time.google.com //samples:5 //dataonly`
  (barras dobradas por causa do Git Bash).

## Comandos
```bash
export GCP_PROJECT=teste-pub-sub-515002      # fish: set -Ux GCP_PROJECT teste-pub-sub-515002
source ~/venvs/iot/bin/activate              # Windows/Git Bash: source ~/venvs/iot/Scripts/activate
pip install -r IoT_setup/requirements.txt
bash IoT_setup/scripts/setup.sh              # uma vez
bash IoT_setup/scripts/run_baseline.sh pc-b <run_id>   # em B, C e D primeiro; depois pc-a
python IoT_setup/src/analyzer.py IoT_setup/dados
bash IoT_setup/scripts/teardown.sh           # ao terminar
```

## Limitações conhecidas (para o artigo)
- A latência compara relógios de máquinas diferentes; o NTP reduz o erro, mas não o elimina.
- O PC B é uma VM dentro do PC A: divide CPU, rede e host com o produtor.
- O PC C está no Wi-Fi 2,4 GHz; os outros no 5 GHz. A comparação C × D em `gases` mostra o efeito da rede.
- Uma única conta Google em todos os PCs.
- Medido no teste `teste/s1` (2026-11-17), mantido como está por decisão do grupo:
  - Relógio do PC A (w32time) ~137 ms atrasado em relação ao `time.google.com`: infla em ~137 ms toda
    latência medida a partir do A (p50 de B/C deu ~200 ms; o real deve estar perto de 63 ms) e distorce a
    separação A→nuvem / nuvem→PC. B e C (chrony) ficaram abaixo de 1 ms.
  - PC D com nuvem→PC ~159 ms contra ~44 ms do C, mesmo estando no 5 GHz (causa não investigada;
    suspeita: economia de energia do Wi-Fi). Afeta a leitura da comparação C × D em `gases`.
  - Relógio do PC D (chrony) entre −7 e −10 ms, pior que B e C.
- O `seek` das assinaturas se propaga de forma assíncrona: publicar logo em seguida gerou reentregas nos
  primeiros ~3 s (por isso o `run_cenario.sh` espera `ESPERA_SEEK` = 10 s antes de publicar).

## Convenções
- Código e comentários em português, sem acentos nos identificadores.
- Python 3.10+. Sem dependências além do `requirements.txt`.
- Bashes com `set -euo pipefail` e mensagem de uso quando faltar argumento.
