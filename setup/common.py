"""Configuracao compartilhada entre client.py e worker.py."""
import os
import sys

PROJECT = os.environ.get("GCP_PROJECT")
if not PROJECT:
    sys.exit("Defina a variavel de ambiente GCP_PROJECT (ex.: export GCP_PROJECT=meu-projeto)")

REQ_TOPIC = "rpc-requests"
REP_TOPIC = "rpc-replies"
REQ_SUB = "rpc-requests-sub"   # compartilhada pelos workers (competing consumers)
REP_SUB = "rpc-replies-sub"    # consumida pelo client
