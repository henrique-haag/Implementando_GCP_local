# Resultados

Warm-up descartado: 10 s iniciais de cada repeticao. Valores: media ± desvio padrao entre repeticoes. Latencia = ts_recebimento − ts_publicacao (primeira entrega de cada seq).

## happy_path / happy-01

Taxa real publicada (PC A, rodada inteira): 19.999 ± 0.000 msgs/s em 3 repeticao(oes); 4200 mensagens no total.

| PC | Assinatura | Reps | Publicadas | Recebidas | Perdas | Perdas (%) | Duplicatas | Vazao (msgs/s) | Lat. media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | A->nuvem p50 (ms) | nuvem->PC p50 (ms) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pc-b | sub-b-ambiente | 3 | 400 ± 0 | 400.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 6.67 ± 0.00 | 106.0 ± 4.2 | 103.5 ± 3.8 | 118.3 ± 7.0 | 155.9 ± 45.5 | 59.3 ± 2.0 | 43.9 ± 2.2 |
| pc-c | sub-c-gases | 3 | 400 ± 0 | 400.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 6.67 ± 0.00 | 111.6 ± 4.9 | 104.9 ± 1.9 | 142.2 ± 41.4 | 264.6 ± 116.0 | 59.3 ± 2.1 | 45.3 ± 0.3 |
| pc-d | sub-d-eventos | 3 | 400 ± 0 | 400.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 6.68 ± 0.02 | 201.4 ± 11.4 | 191.5 ± 6.4 | 382.7 ± 62.7 | 569.9 ± 159.1 | 59.3 ± 2.1 | 131.6 ± 8.5 |
| pc-d | sub-d-gases | 3 | 400 ± 0 | 400.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 6.68 ± 0.03 | 204.0 ± 6.2 | 189.2 ± 1.2 | 389.4 ± 41.3 | 590.2 ± 103.8 | 59.3 ± 2.1 | 128.7 ± 3.2 |

Latencias corrigidas pelo offset do relogio (latencia − offset do consumidor + offset do PC A; offset = media de inicio e fim da repeticao):

| PC | Assinatura | Reps | Lat. media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | A->nuvem p50 (ms) | nuvem->PC p50 (ms) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| pc-b | sub-b-ambiente | 3 | 65.0 ± 2.3 | 62.5 ± 1.7 | 77.2 ± 6.2 | 114.9 ± 44.9 | 17.2 ± 1.3 | 44.9 ± 2.3 |
| pc-c | sub-c-gases | 3 | 69.6 ± 6.4 | 62.8 ± 1.5 | 100.1 ± 43.2 | 222.5 ± 117.6 | 17.3 ± 1.2 | 45.2 ± 0.4 |
| pc-d | sub-d-eventos | 3 | 159.6 ± 12.9 | 149.7 ± 7.8 | 340.9 ± 64.2 | 528.1 ± 160.5 | 17.2 ± 1.2 | 131.8 ± 7.6 |
| pc-d | sub-d-gases | 3 | 162.2 ± 7.6 | 147.4 ± 2.6 | 347.6 ± 42.6 | 548.4 ± 104.0 | 17.3 ± 1.2 | 128.9 ± 2.4 |

Offset do relogio (local − time.google.com, ms; positivo = local adiantado), considerando as medicoes de inicio e fim de todas as repeticoes:

| PC | Min | Max | Media |
|---|---:|---:|---:|
| pc-a | -44.7 | -38.6 | -42.0 |
| pc-b | -1.1 | -1.0 | -1.0 |
| pc-c | -0.3 | 0.4 | 0.1 |
| pc-d | -4.0 | 2.4 | -0.2 |

## teste / s1

Taxa real publicada (PC A, rodada inteira): 10.000 ± 0.000 msgs/s em 2 repeticao(oes); 400 mensagens no total.

| PC | Assinatura | Reps | Publicadas | Recebidas | Perdas | Perdas (%) | Duplicatas | Vazao (msgs/s) | Lat. media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | A->nuvem p50 (ms) | nuvem->PC p50 (ms) |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pc-b | sub-b-ambiente | 2 | 33 ± 0 | 33.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 3.33 ± 0.00 | 200.5 ± 2.7 | 199.2 ± 2.8 | 209.7 ± 1.9 | 212.4 ± 2.5 | 153.8 ± 2.2 | 44.2 ± 2.1 |
| pc-c | sub-c-gases | 2 | 34 ± 0 | 34.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 3.33 ± 0.00 | 199.9 ± 0.1 | 198.5 ± 0.2 | 206.6 ± 2.6 | 215.4 ± 4.8 | 154.0 ± 1.3 | 43.9 ± 1.0 |
| pc-d | sub-d-eventos | 2 | 33 ± 0 | 33.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 3.35 ± 0.04 | 315.6 ± 17.4 | 317.2 ± 5.1 | 412.7 ± 74.5 | 434.4 ± 78.7 | 153.9 ± 1.3 | 159.1 ± 1.3 |
| pc-d | sub-d-gases | 2 | 34 ± 0 | 34.0 ± 0.0 | 0.0 ± 0.0 | 0.00 ± 0.00 | 0.0 ± 0.0 | 3.32 ± 0.00 | 319.6 ± 21.6 | 315.2 ± 6.1 | 434.7 ± 120.9 | 467.4 ± 152.0 | 154.0 ± 1.3 | 159.6 ± 4.2 |

Latencias corrigidas pelo offset do relogio (latencia − offset do consumidor + offset do PC A; offset = media de inicio e fim da repeticao):

| PC | Assinatura | Reps | Lat. media (ms) | p50 (ms) | p95 (ms) | p99 (ms) | A->nuvem p50 (ms) | nuvem->PC p50 (ms) |
|---|---|---|---:|---:|---:|---:|---:|---:|
| pc-b | sub-b-ambiente | 2 | 64.2 ± 0.3 | 62.8 ± 0.4 | 73.3 ± 4.2 | 76.1 ± 4.9 | 17.0 ± 0.1 | 44.7 ± 2.0 |
| pc-c | sub-c-gases | 2 | 62.8 ± 2.3 | 61.4 ± 2.2 | 69.5 ± 5.0 | 78.2 ± 2.4 | 17.1 ± 1.1 | 43.5 ± 1.1 |
| pc-d | sub-d-eventos | 2 | 187.3 ± 14.7 | 188.9 ± 2.4 | 284.4 ± 71.7 | 306.1 ± 76.0 | 17.0 ± 1.0 | 167.6 ± 0.9 |
| pc-d | sub-d-gases | 2 | 191.3 ± 18.8 | 186.9 ± 3.4 | 306.4 ± 118.2 | 339.1 ± 149.3 | 17.1 ± 1.1 | 168.2 ± 3.8 |

Offset do relogio (local − time.google.com, ms; positivo = local adiantado), considerando as medicoes de inicio e fim de todas as repeticoes:

| PC | Min | Max | Media |
|---|---:|---:|---:|
| pc-a | -139.5 | -134.2 | -136.8 |
| pc-b | -0.6 | -0.4 | -0.5 |
| pc-c | 0.3 | 0.4 | 0.3 |
| pc-d | -9.6 | -6.9 | -8.5 |
