#!/usr/bin/env bash
# Logica comum de run_baseline.sh e run_happy_path.sh: roda as repeticoes de um cenario em um PC.
# Uso: bash scripts/run_cenario.sh <cenario> <taxa> <pc-a|pc-b|pc-c|pc-d> <run_id>
#
# Variaveis opcionais: REPS (3), DURACAO (70), IDLE_TIMEOUT (15), PAUSA (IDLE_TIMEOUT + 15).
# Consumidores (pc-b/c/d): rodam uma repeticao atras da outra; cada uma termina pelo idle-timeout.
# Produtor (pc-a): antes de cada repeticao faz seek das 4 assinaturas para "agora" e, entre
# repeticoes, espera PAUSA s para os consumidores fecharem a anterior e abrirem a proxima.
set -euo pipefail

uso() {
    echo "Uso: bash $(basename "$0") <cenario> <taxa> <pc-a|pc-b|pc-c|pc-d> <run_id>" >&2
    exit 1
}
[[ $# -eq 4 ]] || uso
CENARIO="$1"; TAXA="$2"; PC="$3"; RUN_ID="$4"
case "$PC" in pc-a|pc-b|pc-c|pc-d) ;; *) echo "PC invalido: $PC" >&2; uso ;; esac
[[ "$RUN_ID" =~ ^[A-Za-z0-9_.-]+$ ]] || { echo "run_id invalido (use letras, numeros, _ . -): $RUN_ID" >&2; exit 1; }

REPS="${REPS:-3}"
DURACAO="${DURACAO:-70}"
IDLE_TIMEOUT="${IDLE_TIMEOUT:-15}"
PAUSA="${PAUSA:-$((IDLE_TIMEOUT + 15))}"
ASSINATURAS=(sub-b-ambiente sub-c-gases sub-d-gases sub-d-eventos)   # repete src/common.py

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SO="$(uname -s)"

# ---------------------------------------------------------------- checagens
: "${GCP_PROJECT:?Defina GCP_PROJECT (ex.: export GCP_PROJECT=teste-pub-sub-515002)}"
if ! command -v python >/dev/null 2>&1; then
    echo "Erro: 'python' nao encontrado. Ative o venv antes (source ~/venvs/iot/bin/activate)." >&2
    exit 1
fi
if ! python -c "import google.cloud.pubsub" >/dev/null 2>&1; then
    echo "Erro: google-cloud-pubsub nao importa com $(command -v python)." >&2
    echo "Ative o venv e rode: pip install -r IoT_setup/requirements.txt" >&2
    exit 1
fi
if [[ "$PC" == "pc-a" ]] && ! command -v gcloud >/dev/null 2>&1; then
    echo "Erro: gcloud nao encontrado no PATH (necessario no PC A para o seek)." >&2
    exit 1
fi
for rep in $(seq 1 "$REPS"); do
    csv="$RAIZ/dados/$CENARIO/$RUN_ID/rep$rep/$PC.csv"
    if [[ -e "$csv" ]]; then
        echo "Erro: $csv ja existe. Use outro run_id." >&2
        exit 1
    fi
done

trap 'echo; echo "Interrompido."; exit 130' INT

# ---------------------------------------------------------------- funcoes
medir_offset() {
    case "$SO" in
        MINGW*|MSYS*|CYGWIN*)
            w32tm //stripchart //computer:time.google.com //samples:5 //dataonly 2>&1 || echo "w32tm falhou" ;;
        Linux)
            if command -v chronyc >/dev/null 2>&1; then
                chronyc tracking 2>&1 | grep "System time" || echo "chronyc tracking sem linha 'System time'"
            else
                echo "chronyc nao encontrado"
            fi ;;
        *) echo "SO nao suportado para medir offset: $SO" ;;
    esac
}

escrever_meta_inicio() {
    local arq="$1"
    {
        echo "pc: $PC"
        echo "cenario: $CENARIO | run_id: $RUN_ID | rep: $2 | taxa: $TAXA | duracao: $DURACAO"
        echo "hostname: $(hostname)"
        echo "so: $(uname -a)"
        if [[ -r /etc/os-release ]]; then
            echo "distro: $(. /etc/os-release && echo "${PRETTY_NAME:-?}")"
        fi
        if [[ "$SO" == MINGW* || "$SO" == MSYS* ]]; then
            echo "windows: $(cmd //c ver 2>/dev/null | tr -d '\r' | grep -v '^$' || true)"
        fi
        echo "python: $(python --version 2>&1)"
        echo "inicio (utc): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo
        echo "== offset do relogio (inicio) =="
        medir_offset
        echo
        echo "== pip freeze =="
        python -m pip freeze 2>&1
    } > "$arq"
}

escrever_meta_fim() {
    local arq="$1"
    {
        echo
        echo "fim (utc): $(date -u +%Y-%m-%dT%H:%M:%SZ)"
        echo "== offset do relogio (fim) =="
        medir_offset
    } >> "$arq"
}

seek_assinaturas() {
    local agora
    agora="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Seek das assinaturas para $agora (descarta sobras)..."
    for sub in "${ASSINATURAS[@]}"; do
        gcloud pubsub subscriptions seek "$sub" --time="$agora" --project="$GCP_PROJECT" >/dev/null
        echo "  $sub ok"
    done
}

# ---------------------------------------------------------------- execucao
echo "== $CENARIO | $PC | run_id=$RUN_ID | $REPS repeticoes | projeto $GCP_PROJECT =="

if [[ "$PC" == "pc-a" && -t 0 ]]; then
    read -r -p "Os consumidores B, C e D ja estao aguardando com run_id=$RUN_ID? [Enter para comecar] " _
fi

for rep in $(seq 1 "$REPS"); do
    dir="$RAIZ/dados/$CENARIO/$RUN_ID/rep$rep"
    mkdir -p "$dir"
    meta="$dir/meta-$PC.txt"
    echo
    echo "---------- repeticao $rep/$REPS ($(date +%H:%M:%S)) ----------"
    echo "Medindo offset do relogio..."
    escrever_meta_inicio "$meta" "$rep"

    if [[ "$PC" == "pc-a" ]]; then
        seek_assinaturas
        python -u "$RAIZ/src/producer_pc_a.py" --run-id "$RUN_ID" --cenario "$CENARIO" --rep "$rep" \
            --taxa "$TAXA" --duracao "$DURACAO" 2>&1 | tee -i "$dir/log-$PC.txt"
    else
        python -u "$RAIZ/src/consumer_${PC//-/_}.py" --run-id "$RUN_ID" --cenario "$CENARIO" --rep "$rep" \
            --idle-timeout "$IDLE_TIMEOUT" 2>&1 | tee -i "$dir/log-$PC.txt"
    fi

    escrever_meta_fim "$meta"

    if [[ "$PC" == "pc-a" && "$rep" -lt "$REPS" ]]; then
        echo "Pausa de $PAUSA s para os consumidores fecharem a repeticao $rep..."
        sleep "$PAUSA"
    fi
done

echo
echo "Concluido: $RAIZ/dados/$CENARIO/$RUN_ID"
