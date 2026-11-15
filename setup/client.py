"""Client (rodar no PC A): envia requisicoes a taxa constante e mede o RTT.

Todo o RTT e medido com o MESMO relogio (time.perf_counter do PC A),
portanto nao depende de sincronizacao entre os computadores.

Exemplo:
  python setup/client.py --scenario rate --param 100 --rate 100 --duration 60
"""
import argparse
import csv
import json
import os
import threading
import time
import uuid

import numpy as np
from google.cloud import pubsub_v1

import common


def pct(x, q):
    return float(np.percentile(x, q)) if len(x) else float("nan")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", default="baseline", help="nome do cenario (usado nos arquivos)")
    p.add_argument("--param", type=float, default=0, help="valor do parametro variado (eixo X)")
    p.add_argument("--rep", type=int, default=1, help="numero da repeticao")
    p.add_argument("--rate", type=float, default=10, help="requisicoes por segundo")
    p.add_argument("--duration", type=float, default=60, help="duracao do envio (s)")
    p.add_argument("--task", default="echo", choices=["echo", "primes", "sleep"])
    p.add_argument("--n", type=int, default=100000, help="limite do crivo (task=primes)")
    p.add_argument("--ms", type=int, default=50, help="tempo de espera (task=sleep)")
    p.add_argument("--payload", type=int, default=100, help="bytes de padding na requisicao")
    p.add_argument("--batch", type=int, default=1, help="max_messages do batch do publisher")
    p.add_argument("--batch-latency", type=float, default=0.05, help="max_latency do batch (s)")
    p.add_argument("--warmup", type=int, default=20, help="primeiras N requisicoes descartadas")
    p.add_argument("--timeout", type=float, default=30, help="espera por respostas apos o fim do envio (s)")
    p.add_argument("--outdir", default="results")
    a = p.parse_args()
    os.makedirs(a.outdir, exist_ok=True)

    run_id = uuid.uuid4().hex[:8]
    total = int(a.rate * a.duration)
    t_send = [0.0] * total
    recv = {}                       # seq -> (t_recv, proc_ms, worker)
    dups = [0]
    lock = threading.Lock()

    publisher = pubsub_v1.PublisherClient(
        batch_settings=pubsub_v1.types.BatchSettings(
            max_messages=a.batch, max_latency=a.batch_latency if a.batch > 1 else 0.001)
    )
    subscriber = pubsub_v1.SubscriberClient()
    req_path = publisher.topic_path(common.PROJECT, common.REQ_TOPIC)
    rep_path = subscriber.subscription_path(common.PROJECT, common.REP_SUB)

    def on_reply(msg):
        t = time.perf_counter()
        at = msg.attributes
        if at.get("run_id") == run_id:          # ignora sobras de execucoes anteriores
            body = json.loads(msg.data)
            seq = int(at["seq"])
            with lock:
                if seq in recv:
                    dups[0] += 1
                else:
                    recv[seq] = (t, body["proc_ms"], body["worker"])
        msg.ack()

    sub_future = subscriber.subscribe(rep_path, on_reply)
    time.sleep(3)                                # espera o stream de respostas abrir

    data = json.dumps({"task": a.task, "n": a.n, "ms": a.ms, "pad": "x" * a.payload}).encode()
    futures = []
    print(f"run_id={run_id} enviando {total} requisicoes a {a.rate}/s ...", flush=True)

    t0 = time.perf_counter()
    for i in range(total):
        target = t0 + i / a.rate
        while True:                              # espera precisa (sleep + spin)
            d = target - time.perf_counter()
            if d <= 0:
                break
            if d > 0.002:
                time.sleep(d - 0.001)
        t_send[i] = time.perf_counter()
        futures.append(publisher.publish(
            req_path, data, corr_id=f"{run_id}-{i}", run_id=run_id, seq=str(i)))
    t_end_send = time.perf_counter()

    pub_errors = sum(1 for f in futures if f.exception() is not None)

    deadline = time.perf_counter() + a.timeout
    while time.perf_counter() < deadline and len(recv) < total:
        time.sleep(0.1)
    sub_future.cancel()
    subscriber.close()

    # ---------- estatisticas ----------
    valid = range(min(a.warmup, total), total)
    got = [i for i in valid if i in recv]
    rtt = np.array([(recv[i][0] - t_send[i]) * 1000 for i in got])
    proc = np.array([recv[i][1] for i in got])
    lost = len(valid) - len(got)
    span = (max(recv[i][0] for i in got) - t_send[valid[0]]) if got else float("nan")
    workers = {recv[i][2] for i in got}

    row = dict(
        scenario=a.scenario, param=a.param, rep=a.rep, rate=a.rate, task=a.task, n=a.n,
        ms=a.ms, payload=a.payload, batch=a.batch, sent=len(valid), received=len(got),
        lost=lost, dups=dups[0], pub_errors=pub_errors,
        real_send_rate=round(total / (t_end_send - t0), 2),
        throughput=round(len(got) / span, 2) if got else 0,
        mean_ms=round(float(rtt.mean()), 2) if len(rtt) else float("nan"),
        p50_ms=round(pct(rtt, 50), 2), p95_ms=round(pct(rtt, 95), 2),
        p99_ms=round(pct(rtt, 99), 2), max_ms=round(float(rtt.max()), 2) if len(rtt) else float("nan"),
        proc_mean_ms=round(float(proc.mean()), 2) if len(proc) else float("nan"),
        overhead_ms=round(float((rtt - proc).mean()), 2) if len(rtt) else float("nan"),
        workers_seen=len(workers),
    )

    raw = os.path.join(a.outdir, f"raw_{a.scenario}_{a.param:g}_{a.rep}.csv")
    with open(raw, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seq", "warmup", "t_send", "t_recv", "rtt_ms", "proc_ms", "worker"])
        for i in range(total):
            ws = int(i < a.warmup)
            if i in recv:
                tr, pm, wk = recv[i]
                w.writerow([i, ws, round(t_send[i] - t0, 6), round(tr - t0, 6),
                            round((tr - t_send[i]) * 1000, 3), round(pm, 3), wk])
            else:
                w.writerow([i, ws, round(t_send[i] - t0, 6), "", "", "", ""])

    summ = os.path.join(a.outdir, "summary.csv")
    new = not os.path.exists(summ)
    with open(summ, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)

    print(json.dumps(row, indent=2))


if __name__ == "__main__":
    main()
