"""Worker (rodar no PC B): consome requisicoes, processa e publica a resposta.

Exemplos:
  python setup/worker.py --procs 4 --threads 1          # 4 processos, 1 thread cada
  python setup/worker.py --procs 1 --threads 4 --crash-after 300   # falha injetada
  python setup/worker.py --procs 2 --fail-rate 0.2      # nack aleatorio (teste de DLQ)
"""
import argparse
import json
import multiprocessing as mp
import os
import random
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.scheduler import ThreadScheduler

import test_setup.setup.common as common


def count_primes(n):
    """Crivo de Eratostenes: tarefa CPU-bound com custo ajustavel por n."""
    if n < 2:
        return 0
    sieve = bytearray([1]) * (n + 1)
    sieve[0] = sieve[1] = 0
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(range(i * i, n + 1, i)))
    return sum(sieve)


def process(req):
    task = req["task"]
    if task == "echo":      # custo ~0: mede so o middleware
        return len(req.get("pad", ""))
    if task == "primes":    # CPU-bound
        return count_primes(req["n"])
    if task == "sleep":     # I/O-bound simulado, custo previsivel
        time.sleep(req["ms"] / 1000)
        return 0
    raise ValueError(f"tarefa desconhecida: {task}")


def run_worker(wid, a):
    subscriber = pubsub_v1.SubscriberClient()
    publisher = pubsub_v1.PublisherClient(
        batch_settings=pubsub_v1.types.BatchSettings(max_messages=1, max_latency=0.001)
    )
    sub_path = subscriber.subscription_path(common.PROJECT, common.REQ_SUB)
    rep_path = publisher.topic_path(common.PROJECT, common.REP_TOPIC)
    counter = [0]
    lock = threading.Lock()

    def callback(msg):
        if a.fail_rate and random.random() < a.fail_rate:
            msg.nack()                      # forca reentrega / eventual DLQ
            return
        with lock:
            counter[0] += 1
            if a.crash_after and counter[0] > a.crash_after:
                os._exit(1)                 # simula queda: morre sem dar ack
        try:
            t0 = time.perf_counter()
            req = json.loads(msg.data)
            result = process(req)
            proc_ms = (time.perf_counter() - t0) * 1000
            body = json.dumps({"result": result, "proc_ms": proc_ms, "worker": wid}).encode()
            attrs = {k: msg.attributes[k] for k in ("corr_id", "run_id", "seq")}
            publisher.publish(rep_path, body, **attrs).result(timeout=30)
            msg.ack()                       # ack so depois de a resposta ser publicada
        except Exception as e:
            print(f"[{wid}] erro: {e}")
            msg.nack()

    flow = pubsub_v1.types.FlowControl(max_messages=a.threads * 2)
    scheduler = ThreadScheduler(ThreadPoolExecutor(max_workers=a.threads))
    future = subscriber.subscribe(sub_path, callback, flow_control=flow, scheduler=scheduler)
    print(f"[{wid}] pronto (threads={a.threads})", flush=True)
    try:
        future.result()
    except KeyboardInterrupt:
        future.cancel()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--procs", type=int, default=1, help="numero de processos worker")
    ap.add_argument("--threads", type=int, default=4, help="threads por processo")
    ap.add_argument("--fail-rate", type=float, default=0.0, help="fracao de nacks aleatorios")
    ap.add_argument("--crash-after", type=int, default=0, help="morre apos N mensagens (0 = nunca)")
    a = ap.parse_args()

    host = socket.gethostname()
    procs = [mp.Process(target=run_worker, args=(f"{host}-{i}", a)) for i in range(a.procs)]
    for p in procs:
        p.start()
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
