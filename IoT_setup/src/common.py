"""Codigo comum do prototipo Pub/Sub IoT: nomes, mensagem, CSV, timestamps e o laco do consumidor.

Os nomes de topicos e assinaturas sao repetidos em scripts/setup.sh e scripts/teardown.sh.
"""

import argparse
import csv
import json
import os
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------- nomes e caminhos

RAIZ = Path(__file__).resolve().parent.parent          # IoT_setup/
DATASET_PADRAO = RAIZ / "dataset" / "iot_telemetry_data.csv"
DIR_DADOS = RAIZ / "dados"

# topico -> leituras (colunas do dataset) que vao no payload
TOPICOS = {
    "ambiente": ["temp", "humidity"],
    "gases": ["co", "lpg", "smoke"],
    "eventos": ["motion", "light"],
}

# assinatura -> topico
ASSINATURAS = {
    "sub-b-ambiente": "ambiente",
    "sub-c-gases": "gases",
    "sub-d-gases": "gases",
    "sub-d-eventos": "eventos",
}

# pc -> assinaturas que ele consome (uma assinatura por PC: fan-out)
PCS = {
    "pc-b": ["sub-b-ambiente"],
    "pc-c": ["sub-c-gases"],
    "pc-d": ["sub-d-gases", "sub-d-eventos"],
}

COLUNAS_DATASET = ["ts", "device", "co", "humidity", "light", "lpg", "motion", "smoke", "temp"]
LEITURAS_BOOL = {"light", "motion"}

COLUNAS_PRODUTOR = [
    "run_id", "cenario", "rep", "topico", "device_id", "seq",
    "ts_evento", "ts_publicacao", "message_id",
]
COLUNAS_CONSUMIDOR = [
    "run_id", "cenario", "rep", "pc", "assinatura", "topico", "device_id", "seq", "message_id",
    "ts_publicacao", "publish_time_servidor", "ts_recebimento",
]

IDLE_TIMEOUT_PADRAO = 15.0


def projeto():
    p = os.environ.get("GCP_PROJECT")
    if not p:
        sys.exit("Erro: defina GCP_PROJECT (ex.: export GCP_PROJECT=teste-pub-sub-515002)")
    return p


def importar_pubsub():
    """Importa pubsub_v1 com uma mensagem clara se o venv nao tiver as dependencias."""
    try:
        from google.cloud import pubsub_v1
    except ImportError:
        sys.exit("Erro: google-cloud-pubsub nao esta instalado neste Python "
                 f"({sys.executable}).\nAtive o venv e rode: pip install -r IoT_setup/requirements.txt")
    return pubsub_v1


def agora_ms():
    """Relogio de parede em epoch ms (float). Obrigatorio para comparar maquinas diferentes."""
    return time.time() * 1000.0


def dir_rodada(cenario, run_id, rep):
    return DIR_DADOS / cenario / run_id / f"rep{rep}"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- argumentos

def parser_base(descricao):
    p = argparse.ArgumentParser(description=descricao)
    p.add_argument("--run-id", required=True, help="identificador da rodada (igual em todos os PCs)")
    p.add_argument("--cenario", default="teste", help="baseline, happy_path, teste... (padrao: teste)")
    p.add_argument("--rep", type=int, default=1, help="numero da repeticao (padrao: 1)")
    p.add_argument("--sobrescrever", action="store_true", help="sobrescreve o CSV se ja existir")
    return p


# ---------------------------------------------------------------- dataset e mensagem

def _converter(coluna, valor):
    if coluna in LEITURAS_BOOL:
        return valor.strip().lower() == "true"
    return float(valor)


def ler_dataset(caminho=DATASET_PADRAO):
    """Gera as linhas do dataset (dict) indefinidamente, recomecando do inicio quando o arquivo acaba."""
    caminho = Path(caminho)
    if not caminho.exists():
        sys.exit(f"Erro: dataset nao encontrado em {caminho}")
    while True:
        with open(caminho, newline="", encoding="utf-8") as f:
            leitor = csv.DictReader(f)
            faltando = set(COLUNAS_DATASET) - set(leitor.fieldnames or [])
            if faltando:
                sys.exit(f"Erro: colunas ausentes no dataset: {sorted(faltando)}")
            n = 0
            for linha in leitor:
                n += 1
                yield linha
        if n == 0:
            sys.exit("Erro: dataset vazio")
        log("Dataset chegou ao fim; recomecando do inicio (replay).")


def montar_mensagem(topico, linha, run_id, seq, ts_publicacao):
    """Devolve (bytes do payload JSON, atributos, ts_evento) para uma linha do dataset."""
    ts_evento = float(linha["ts"]) * 1000.0
    payload = {
        "run_id": run_id,
        "seq": seq,
        "device_id": linha["device"],
        "ts_evento": ts_evento,
        "ts_publicacao": ts_publicacao,
    }
    for col in TOPICOS[topico]:
        payload[col] = _converter(col, linha[col])
    atributos = {"run_id": run_id, "device_id": linha["device"], "tipo": topico}
    return json.dumps(payload).encode("utf-8"), atributos, ts_evento


# ---------------------------------------------------------------- CSV

class GravadorCsv:
    """Escrita de CSV segura entre threads; faz flush a cada linha (o ack so vem depois da gravacao)."""

    def __init__(self, caminho, colunas, sobrescrever=False):
        self.caminho = Path(caminho)
        if self.caminho.exists() and not sobrescrever:
            sys.exit(f"Erro: {self.caminho} ja existe. Use outro --run-id/--rep ou --sobrescrever.")
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._arquivo = open(self.caminho, "w", newline="", encoding="utf-8")
        self._escritor = csv.DictWriter(self._arquivo, fieldnames=colunas)
        self._escritor.writeheader()
        self._arquivo.flush()
        self.linhas = 0
        self.fechado = False

    def gravar(self, linha):
        """Grava a linha; devolve False se o arquivo ja foi fechado."""
        with self._lock:
            if self.fechado:
                return False
            self._escritor.writerow(linha)
            self._arquivo.flush()
            self.linhas += 1
            return True

    def fechar(self):
        with self._lock:
            if not self.fechado:
                self.fechado = True
                self._arquivo.close()


# ---------------------------------------------------------------- consumidor

def rodar_consumidor(pc):
    """Laco completo de um PC consumidor: streaming pull em todas as assinaturas do PC,
    ack manual depois de gravar no CSV, encerramento apos --idle-timeout sem mensagens."""
    assinaturas = PCS[pc]
    p = parser_base(f"Consumidor {pc}: {', '.join(assinaturas)}")
    p.add_argument("--idle-timeout", type=float, default=IDLE_TIMEOUT_PADRAO,
                   help="encerra apos N s sem mensagens da rodada, contados a partir da primeira (padrao: 15)")
    args = p.parse_args()

    pubsub_v1 = importar_pubsub()

    proj = projeto()
    caminho = dir_rodada(args.cenario, args.run_id, args.rep) / f"{pc}.csv"
    gravador = GravadorCsv(caminho, COLUNAS_CONSUMIDOR, args.sobrescrever)

    estado = {
        "recebidas": {s: 0 for s in assinaturas},
        "ignoradas": 0,        # run_id diferente
        "invalidas": 0,        # payload ilegivel
        "ultima": None,        # monotonic da ultima mensagem valida
    }
    lock = threading.Lock()

    def fazer_callback(assinatura):
        topico = ASSINATURAS[assinatura]

        def callback(message):
            ts_recebimento = agora_ms()
            try:
                payload = json.loads(message.data.decode("utf-8"))
                run_id = payload.get("run_id")
            except (ValueError, UnicodeDecodeError, AttributeError):
                with lock:
                    estado["invalidas"] += 1
                message.ack()
                return
            if run_id != args.run_id:
                with lock:
                    estado["ignoradas"] += 1
                message.ack()
                return
            linha = {
                "run_id": run_id,
                "cenario": args.cenario,
                "rep": args.rep,
                "pc": pc,
                "assinatura": assinatura,
                "topico": topico,
                "device_id": payload.get("device_id", ""),
                "seq": payload.get("seq", ""),
                "message_id": message.message_id,
                "ts_publicacao": payload.get("ts_publicacao", ""),
                "publish_time_servidor": message.publish_time.timestamp() * 1000.0,
                "ts_recebimento": ts_recebimento,
            }
            if gravador.gravar(linha):
                message.ack()
                with lock:
                    estado["recebidas"][assinatura] += 1
                    estado["ultima"] = time.monotonic()
            else:
                message.nack()   # arquivo ja fechado: devolve para o Pub/Sub

        return callback

    subscriber = pubsub_v1.SubscriberClient()
    futuros = {}
    for s in assinaturas:
        caminho_sub = subscriber.subscription_path(proj, s)
        futuros[s] = subscriber.subscribe(caminho_sub, callback=fazer_callback(s))
        log(f"Ouvindo {caminho_sub}")
    log(f"{pc} | run_id={args.run_id} cenario={args.cenario} rep={args.rep} -> {caminho}")
    log(f"Aguardando a primeira mensagem (idle-timeout de {args.idle_timeout:.0f} s comeca a contar nela; Ctrl+C para sair)")

    ultimo_relatorio = time.monotonic()
    motivo = "idle-timeout"
    try:
        while True:
            time.sleep(0.5)
            agora = time.monotonic()
            for s, f in futuros.items():
                if f.done():
                    # o streaming pull morreu: mostra o erro e encerra
                    exc = f.exception()
                    raise RuntimeError(f"Streaming pull de {s} encerrou: {exc!r}")
            with lock:
                ultima = estado["ultima"]
                resumo = dict(estado["recebidas"])
            if agora - ultimo_relatorio >= 5:
                ultimo_relatorio = agora
                log("recebidas: " + ", ".join(f"{s}={n}" for s, n in resumo.items()))
            if ultima is not None and agora - ultima >= args.idle_timeout:
                break
    except KeyboardInterrupt:
        motivo = "Ctrl+C"
    finally:
        for f in futuros.values():
            f.cancel()
        for f in futuros.values():
            try:
                f.result(timeout=10)
            except Exception:
                pass
        subscriber.close()
        gravador.fechar()

    log(f"Encerrado ({motivo}).")
    for s, n in estado["recebidas"].items():
        log(f"  {s}: {n} mensagens gravadas")
    log(f"  ignoradas (outro run_id): {estado['ignoradas']}")
    if estado["invalidas"]:
        log(f"  invalidas (payload ilegivel): {estado['invalidas']}")
    log(f"  CSV: {caminho} ({gravador.linhas} linhas)")
