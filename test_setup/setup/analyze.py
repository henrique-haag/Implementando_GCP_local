"""Gera tabela (markdown/CSV) e graficos a partir de results/.
Uso (da raiz do repo): python setup/analyze.py [pasta_resultados]
"""
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # raiz do repo
R = sys.argv[1] if len(sys.argv) > 1 else "results"
if not os.path.isdir(R) and os.path.isdir(os.path.join(ROOT, R)):
    R = os.path.join(ROOT, R)    # caminho relativo a raiz do repo (ex.: rodando de dentro de setup/)
if not os.path.exists(os.path.join(R, "summary.csv")):
    sys.exit(f"Nao achei {os.path.join(R, 'summary.csv')}. Rode os cenarios antes ou passe a pasta certa.")
df = pd.read_csv(os.path.join(R, "summary.csv"))

METRICS = ["mean_ms", "p50_ms", "p95_ms", "p99_ms", "throughput", "lost", "dups", "overhead_ms"]

# ---------- tabela: media +- desvio entre repeticoes ----------
g = df.groupby(["scenario", "param"])[METRICS].agg(["mean", "std"])
rows = []
for (sc, par), r in g.iterrows():
    cells = [sc, f"{par:g}"]
    for m in METRICS:
        mu, sd = r[(m, "mean")], r[(m, "std")]
        cells.append(f"{mu:.1f} ± {0 if pd.isna(sd) else sd:.1f}")
    rows.append(cells)
header = ["Cenário", "Param"] + METRICS
md = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
md += ["| " + " | ".join(c) + " |" for c in rows]
with open(os.path.join(R, "tabela.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(md))
g.to_csv(os.path.join(R, "tabela.csv"))
print("\n".join(md))


def save(fig, name):
    fig.savefig(os.path.join(R, name), dpi=150, bbox_inches="tight")
    plt.close(fig)


def lat_plot(sc, xlabel, logx=False):
    d = df[df.scenario == sc]
    if d.empty:
        return
    gg = d.groupby("param")
    fig, ax = plt.subplots(figsize=(6, 4))
    for m, lab in [("p50_ms", "p50"), ("p95_ms", "p95"), ("p99_ms", "p99")]:
        ax.errorbar(gg[m].mean().index, gg[m].mean(), yerr=gg[m].std().fillna(0),
                    marker="o", capsize=3, label=lab)
    if logx:
        ax.set_xscale("log")
    ax.set_xlabel(xlabel)
    ax.set_ylabel("RTT (ms)")
    ax.set_title(f"Latência RTT – cenário '{sc}'")
    ax.grid(alpha=.3)
    ax.legend()
    save(fig, f"lat_{sc}.png")


def thr_plot(sc, xlabel):
    d = df[df.scenario == sc]
    if d.empty:
        return
    gg = d.groupby("param")["throughput"]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([f"{x:g}" for x in gg.mean().index], gg.mean(), yerr=gg.std().fillna(0), capsize=4)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Vazão (respostas/s)")
    ax.set_title(f"Vazão – cenário '{sc}'")
    ax.grid(axis="y", alpha=.3)
    save(fig, f"thr_{sc}.png")


def raw(sc):
    fs = sorted(glob.glob(os.path.join(R, f"raw_{sc}_*.csv")))
    return [pd.read_csv(f) for f in fs]


lat_plot("rate", "Taxa de requisições (req/s)")
lat_plot("payload", "Tamanho do payload (bytes)", logx=True)
lat_plot("cost", "Custo da tarefa (n do crivo)", logx=True)
lat_plot("batch", "Tamanho do batch (mensagens)", logx=True)
lat_plot("workers", "Nº de processos worker")
lat_plot("topology", "Topologia (1 = tudo no PC A, 2 = A→B)")
thr_plot("rate", "Taxa de requisições (req/s)")
thr_plot("workers", "Nº de processos worker")

# CDF do baseline
bl = raw("baseline")
if bl:
    x = pd.concat(bl).query("warmup == 0")["rtt_ms"].dropna().sort_values()
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x, [(i + 1) / len(x) for i in range(len(x))])
    ax.set_xlabel("RTT (ms)")
    ax.set_ylabel("Fração acumulada")
    ax.set_title("CDF do RTT – baseline")
    ax.grid(alpha=.3)
    save(fig, "cdf_baseline.png")

# Linha do tempo do cenario de falha
for i, f in enumerate(raw("fault")):
    f = f[f.warmup == 0]
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7, 6), sharex=True)
    a1.scatter(f["t_send"], f["rtt_ms"], s=6)
    a1.set_ylabel("RTT (ms)")
    a1.set_title("Cenário de falha: RTT por requisição")
    a1.grid(alpha=.3)
    rec = f["t_recv"].dropna()
    a2.hist(rec, bins=range(0, int(rec.max()) + 2))
    a2.set_xlabel("Tempo desde o início (s)")
    a2.set_ylabel("Respostas recebidas/s")
    a2.grid(alpha=.3)
    save(fig, f"timeline_fault_{i + 1}.png")

print(f"\nGráficos e tabelas salvos em {R}/")
