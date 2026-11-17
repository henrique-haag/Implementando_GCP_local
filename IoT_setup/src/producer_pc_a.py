"""PC A: publica o dataset nos topicos a uma taxa constante (open loop).

Cada linha do dataset gera uma mensagem por topico, com o mesmo ts_evento. O seq e global
entre os topicos. A taxa (--taxa) e o total de mensagens/s publicadas, somando os topicos.

Uso: python src/producer_pc_a.py --run-id <id> [--cenario teste] [--rep 1]
         [--taxa 10] [--duracao 70] [--topicos ambiente gases eventos]
"""

import threading
import time

from common import (COLUNAS_PRODUTOR, DATASET_PADRAO, TOPICOS, GravadorCsv, agora_ms,
                    dir_rodada, importar_pubsub, ler_dataset, log, montar_mensagem, parser_base, projeto)


def main():
    p = parser_base("Produtor (PC A)")
    p.add_argument("--taxa", type=float, default=10.0, help="mensagens/s publicadas no total (padrao: 10)")
    p.add_argument("--duracao", type=float, default=70.0, help="duracao em segundos (padrao: 70)")
    p.add_argument("--topicos", nargs="+", choices=list(TOPICOS), default=list(TOPICOS),
                   help="topicos a publicar (padrao: os 3)")
    p.add_argument("--dataset", default=str(DATASET_PADRAO), help="caminho do CSV do Kaggle")
    args = p.parse_args()
    if args.taxa <= 0 or args.duracao <= 0:
        p.error("--taxa e --duracao devem ser positivos")

    pubsub_v1 = importar_pubsub()

    proj = projeto()
    # max_messages=1: cada publish sai na hora, sem esperar lote (o lote somaria atraso a latencia)
    publisher = pubsub_v1.PublisherClient(batch_settings=pubsub_v1.types.BatchSettings(max_messages=1))
    caminhos = {t: publisher.topic_path(proj, t) for t in args.topicos}

    caminho_csv = dir_rodada(args.cenario, args.run_id, args.rep) / "pc-a.csv"
    gravador = GravadorCsv(caminho_csv, COLUNAS_PRODUTOR, args.sobrescrever)

    total = int(round(args.taxa * args.duracao))
    intervalo = 1.0 / args.taxa
    lock = threading.Lock()
    cont = {"ok": 0, "erro": 0}
    pendentes = []

    def ao_concluir(base):
        def cb(futuro):
            try:
                message_id = futuro.result()
            except Exception as exc:
                with lock:
                    cont["erro"] += 1
                log(f"Falha ao publicar seq={base['seq']} ({base['topico']}): {exc!r}")
                return
            gravador.gravar({**base, "message_id": message_id})
            with lock:
                cont["ok"] += 1
        return cb

    log(f"PC A | run_id={args.run_id} cenario={args.cenario} rep={args.rep} | "
        f"{args.taxa:g} msgs/s por {args.duracao:g} s = {total} mensagens em {args.topicos}")
    log(f"CSV: {caminho_csv}")

    linhas = ler_dataset(args.dataset)
    seq = 0
    atrasadas = 0
    t0 = time.perf_counter()        # perf_counter so para agendar; timestamps usam o relogio de parede
    prim_pub = ult_pub = None
    proximo_relatorio = t0 + 5
    try:
        while seq < total:
            linha = next(linhas)
            for topico in args.topicos:
                if seq >= total:
                    break
                alvo = t0 + seq * intervalo
                espera = alvo - time.perf_counter()
                if espera > 0:
                    time.sleep(espera)
                elif espera < -intervalo:
                    atrasadas += 1
                ts_publicacao = agora_ms()
                dados, atributos, ts_evento = montar_mensagem(topico, linha, args.run_id, seq, ts_publicacao)
                futuro = publisher.publish(caminhos[topico], dados, **atributos)
                base = {
                    "run_id": args.run_id, "cenario": args.cenario, "rep": args.rep,
                    "topico": topico, "device_id": linha["device"], "seq": seq,
                    "ts_evento": ts_evento, "ts_publicacao": ts_publicacao,
                }
                futuro.add_done_callback(ao_concluir(base))
                pendentes.append(futuro)
                prim_pub = prim_pub if prim_pub is not None else ts_publicacao
                ult_pub = ts_publicacao
                seq += 1
                if time.perf_counter() >= proximo_relatorio:
                    proximo_relatorio += 5
                    with lock:
                        log(f"publicadas {seq}/{total} (confirmadas {cont['ok']}, erros {cont['erro']})")
    except KeyboardInterrupt:
        log("Interrompido (Ctrl+C); aguardando as publicacoes pendentes.")

    log("Aguardando confirmacoes do servidor...")
    for f in pendentes:
        try:
            f.result(timeout=60)
        except Exception:
            pass   # ja contado no callback
    # os callbacks rodam em outra thread; da um instante para os ultimos gravarem
    for _ in range(50):
        with lock:
            if cont["ok"] + cont["erro"] >= len(pendentes):
                break
        time.sleep(0.1)
    publisher.stop()
    gravador.fechar()

    duracao_real = (ult_pub - prim_pub) / 1000.0 if seq > 1 else 0.0
    taxa_real = (seq - 1) / duracao_real if duracao_real > 0 else 0.0
    log("Resumo:")
    log(f"  enviadas: {seq} | confirmadas: {cont['ok']} | erros: {cont['erro']}")
    log(f"  taxa alvo: {args.taxa:g} msgs/s | taxa real: {taxa_real:.3f} msgs/s em {duracao_real:.2f} s")
    log(f"  envios com atraso > 1 intervalo: {atrasadas}")
    log(f"  CSV: {caminho_csv} ({gravador.linhas} linhas)")


if __name__ == "__main__":
    main()
