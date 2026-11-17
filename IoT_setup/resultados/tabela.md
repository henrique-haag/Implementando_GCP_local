# Resultados

Warm-up descartado: 10 s iniciais de cada repeticao. Valores: media ± desvio padrao entre repeticoes. Latencia = ts_recebimento − ts_publicacao (primeira entrega de cada seq).

## teste / t1

Taxa real publicada (PC A, rodada inteira): 5.000 msgs/s em 1 repeticao(oes); 100 mensagens no total.

| PC | Assinatura | Reps | Publicadas | Recebidas | Perdas | Perdas (%) | Duplicatas | Vazao (msgs/s) | Lat. media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | A->nuvem p50 (ms) | nuvem->PC p50 (ms) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pc-b | sub-b-ambiente | 1 | 50 | 50.0 | 0.0 | 0.00 | 0.0 | 5.01 | 63.2 | 56.7 | 111.4 | 125.5 | 201.6 | -144.5 |
