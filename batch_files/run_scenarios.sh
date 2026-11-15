#!/usr/bin/env bash
# Rodar no PC A. Cada cenario e repetido REPS vezes (padrao 3).
# Uso: ./run_scenarios.sh <cenario> [parametro]
REPS=${REPS:-3}
DUR=${DUR:-60}

run() {  # run <cenario> <param> <args do client...>
  local sc=$1 param=$2; shift 2
  for r in $(seq "$REPS"); do
    python client.py --scenario "$sc" --param "$param" --rep "$r" --duration "$DUR" "$@"
    sleep 5   # deixa o backlog esvaziar entre repeticoes
  done
}

case "$1" in
  baseline) run baseline 10 --rate 10 ;;
  rate)     for x in 10 50 100 200 500; do run rate $x --rate $x; done ;;
  payload)  for x in 100 1000 10000 100000; do run payload $x --rate 20 --payload $x; done ;;
  cost)     for x in 10000 100000 1000000 5000000; do run cost $x --rate 5 --task primes --n $x; done ;;
  batch)    for x in 1 10 100; do run batch $x --rate 500 --batch $x; done ;;
  # $2 = numero de processos worker ligados (workers com --threads 1 => ~10 req/s cada)
  workers)  DUR=30 run workers "$2" --rate 80 --task sleep --ms 100 ;;
  # $2 = 1 (tudo no PC A) ou 2 (client no A, workers no B)
  topology) run topology "$2" --rate 50 ;;
  # $2 = ack deadline configurado (s). Matar/derrubar um worker durante a execucao.
  fault)    DUR=90 REPS=1 run fault "$2" --rate 20 --task sleep --ms 100 --timeout 60 ;;
  # $2 = taxa de nack usada nos workers (ex.: 0.2)
  nack)     run nack "$2" --rate 20 ;;
  *) echo "cenarios: baseline rate payload cost batch workers topology fault nack"; exit 1 ;;
esac
