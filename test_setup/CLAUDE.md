# CLAUDE.md

Trabalho de faculdade (Grau B, em grupo): protótipo **Request/Reply sobre Google Cloud Pub/Sub**
para medir latência (RTT), vazão e comportamento sob falha. Entregas: apresentação (aula 16) e
artigo em LaTeX no modelo SBC (até a prova do GB).

## Arquitetura
- **PC A** → `client.py`: publica em `rpc-requests` a taxa constante (open loop) e consome `rpc-replies`.
- **PC B** → `worker.py`: N processos na mesma subscription `rpc-requests-sub` (competing consumers),
  processa e publica a resposta em `rpc-replies`.
- **Nuvem**: Pub/Sub. DLQ `rpc-requests-dlq` após 5 tentativas de entrega.
- Correlação por atributos `corr_id`, `run_id` e `seq` (copiados da requisição para a resposta).

## Estrutura
```
batch_files/   setup.sh (cria recursos), teardown.sh (apaga), run_scenarios.sh (roda cenários),
               budget.sh (alerta de orçamento; só avisa, não bloqueia)
setup/         client.py, worker.py, common.py (config), analyze.py (tabelas e gráficos)
requirements.txt, README.md
```
`results/` (gerado): `raw_<cenario>_<param>_<rep>.csv`, `summary.csv`, `tabela.md`/`.csv`, PNGs.

## Comandos
```bash
pip install -r requirements.txt
gcloud auth application-default login
export GCP_PROJECT=<projeto>                 # PowerShell: $env:GCP_PROJECT="<projeto>"
./batch_files/setup.sh 10                    # 10 = ack deadline (s); uma vez
python setup/worker.py --procs 1 --threads 4 # PC B
./batch_files/run_scenarios.sh baseline      # PC A
python setup/analyze.py results
./batch_files/teardown.sh                    # ao terminar
```
Cenários: `baseline rate payload cost batch workers topology fault nack` (mínimo viável:
baseline, rate, payload, workers, fault). Tabela de comandos PC A × PC B no README.

## Decisões de projeto (não alterar sem discutir)
- **RTT medido só com `time.perf_counter()` do PC A** → dispensa sincronizar relógios. Nunca
  comparar timestamps de máquinas diferentes.
- **Ack só depois de publicar a resposta** (at-least-once). Duplicatas são contadas, não evitadas.
- **Gerador open loop** (taxa fixa, independe das respostas). Conferir `real_send_rate ≈ rate`;
  se não, o gargalo é o gerador em Python, não o Pub/Sub.
- Worker devolve `proc_ms` → `overhead_ms = RTT − proc_ms` isola o custo do middleware.
- Tarefas: `echo` (só middleware), `primes` (CPU), `sleep` (custo previsível).
- Metodologia: 3 repetições por ponto (média ± desvio), requisições enviadas nos primeiros 10 s descartadas (warm-up, `--warmup-s`); durações já incluem esses 10 s.
- Client ignora respostas com `run_id` diferente (sobras de execuções anteriores).

## Convenções
- Python 3, scripts simples e autocontidos; sem frameworks além do `requirements.txt`.
- Comentários e mensagens em português, sem acentos no código (strings de gráfico podem ter).
- Nomes de tópicos/subscriptions só em `common.py` e nos `.sh` — manter os dois em sincronia.
- Novas métricas: adicionar ao `row` do `client.py` **e** a `METRICS` no `analyze.py`.
- Novo cenário: entrada no `case` do `run_scenarios.sh`, gráfico no `analyze.py` e linha no README.

## Cuidados
- Os `.sh` chamam os `.py` por caminho; após mudar pastas, conferir caminhos no
  `run_scenarios.sh` e no README.
- `common.py` encerra o programa se `GCP_PROJECT` não estiver definido.
- Os `.sh` precisam de bash (Git Bash/WSL no Windows).
- Não rodar comandos `gcloud` que criem/apaguem recursos sem pedir confirmação (custo e dados do grupo).
- Código validado só com dados sintéticos; ainda não rodou contra o Pub/Sub real.

## Pendências
- Baseline curto no GCP para validar o código.
- Verificar se o pico de recuperação no cenário `fault` fica próximo do ack deadline (10 s × 30 s).
- Relatório LaTeX (SBC): estratégia, arquitetura, metodologia, cenários, gráficos, tabela,
  discussão e limitações.
