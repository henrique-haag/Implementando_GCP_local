"""Analisa os CSVs das rodadas e gera tabelas e graficos em resultados/.
 
Percorre <dir>/<cenario>/<run_id>/rep<N>/, junta pc-a.csv com pc-b/c/d.csv por (run_id, rep, seq) e
calcula, por PC e por assinatura: latencia (media, p50, p95, p99), vazao recebida, perdas e duplicatas.
As mensagens publicadas nos primeiros --warmup segundos de cada repeticao sao descartadas.
 
Latencia = ts_recebimento - ts_publicacao, usando a primeira entrega de cada seq (duplicatas ficam
so na contagem). Os valores por repeticao sao agregados como media +- desvio padrao entre repeticoes.
 
Correcao de relogio: cada meta-<pc>.txt traz o offset do relogio (local - time.google.com) no inicio e
no fim da repeticao. O offset da repeticao e a media dos dois. Com ele:
  latencia_corr = latencia - offset_consumidor + offset_pc_a
  a_nuvem_corr  = a_nuvem  + offset_pc_a          (publish_time e do servidor, ja na referencia)
  nuvem_pc_corr = nuvem_pc - offset_consumidor
As metricas brutas continuam na tabela; as corrigidas ganham o sufixo _corr. Os graficos usam a
latencia corrigida (--sem-correcao volta para a bruta).
 
Uso: python src/analyzer.py IoT_setup/dados [--warmup 10] [--saida IoT_setup/resultados] [--sem-correcao]
"""
 
import argparse
import re
import sys
from pathlib import Path
 
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
 
from common import ASSINATURAS, PCS, RAIZ
 
# Cor fixa por assinatura em todos os graficos (paleta categorica validada para linhas, em ordem fixa)
# e estilo de linha como codificacao secundaria (impressao em P&B / daltonismo).
ESTILO = {
    "sub-b-ambiente": {"color": "#2a78d6", "linestyle": "-"},
    "sub-c-gases":    {"color": "#eb6834", "linestyle": "--"},
    "sub-d-gases":    {"color": "#1baf7a", "linestyle": "-."},
    "sub-d-eventos":  {"color": "#eda100", "linestyle": ":"},
}
COR_TEXTO = "#0b0b0b"
COR_SECUNDARIA = "#52514e"
COR_GRADE = "#e4e3df"
 
METRICAS = [
    # coluna, rotulo na tabela.md, casas decimais
    ("publicadas", "Publicadas", 0),
    ("recebidas", "Recebidas", 1),
    ("perdas", "Perdas", 1),
    ("perdas_pct", "Perdas (%)", 2),
    ("duplicatas", "Duplicatas", 1),
    ("vazao", "Vazao (msgs/s)", 2),
    ("lat_media", "Lat. media (ms)", 1),
    ("lat_p50", "p50 (ms)", 1),
    ("lat_p95", "p95 (ms)", 1),
    ("lat_p99", "p99 (ms)", 1),
    ("a_nuvem_p50", "A->nuvem p50 (ms)", 1),
    ("nuvem_pc_p50", "nuvem->PC p50 (ms)", 1),
]
 
# Mesmas latencias, corrigidas pelo offset do relogio (segunda tabela do tabela.md)
METRICAS_CORR = [
    ("lat_media_corr", "Lat. media (ms)", 1),
    ("lat_p50_corr", "p50 (ms)", 1),
    ("lat_p95_corr", "p95 (ms)", 1),
    ("lat_p99_corr", "p99 (ms)", 1),
    ("a_nuvem_p50_corr", "A->nuvem p50 (ms)", 1),
    ("nuvem_pc_p50_corr", "nuvem->PC p50 (ms)", 1),
]
 
# Diferenca entre o offset do inicio e o do fim acima da qual o analyzer avisa (relogio andou na rep)
LIMITE_DERIVA_MS = 5.0
 
 
def aviso(msg):
    print(f"AVISO: {msg}", file=sys.stderr)
 
 
# ---------------------------------------------------------------- leitura
 
def descobrir_reps(raiz):
    """Lista (cenario, run_id, rep, dir) para cada pasta rep<N> com um pc-a.csv."""
    reps = []
    for d in sorted(raiz.rglob("rep*")):
        m = re.fullmatch(r"rep(\d+)", d.name)
        if not (d.is_dir() and m):
            continue
        if not (d / "pc-a.csv").exists():
            aviso(f"{d} sem pc-a.csv (referencia das perdas); ignorado")
            continue
        reps.append((d.parent.parent.name, d.parent.name, int(m.group(1)), d))
    return reps
 
 
def ler_offsets(d, cenario, run_id, rep):
    """Le os meta-<pc>.txt e devolve o offset do relogio local (local - referencia, em ms) no inicio e no fim.
    Positivo = relogio local adiantado."""
    linhas = []
    for meta in sorted(d.glob("meta-*.txt")):
        pc = meta.stem.removeprefix("meta-")
        texto = meta.read_text(encoding="utf-8", errors="replace")
        valores = {}
        for momento in ("inicio", "fim"):
            m = re.search(rf"== offset do relogio \({momento}\) ==\n(.*?)(?:\n==|\Z)", texto, re.S)
            bloco = m.group(1) if m else ""
            # w32tm stripchart: "hh:mm:ss, +00.1795042s" (positivo = referencia a frente do local)
            w32 = [float(x) for x in re.findall(r",\s*([+-]\d+\.\d+)s", bloco)]
            # chronyc tracking: "System time : 0.000012 seconds fast of NTP time"
            chrony = re.search(r"System time\s*:\s*([\d.]+) seconds (fast|slow)", bloco)
            if w32:
                valores[momento] = -np.mean(w32) * 1000.0
            elif chrony:
                v = float(chrony.group(1)) * 1000.0
                valores[momento] = v if chrony.group(2) == "fast" else -v
            else:
                valores[momento] = np.nan
        linhas.append({"cenario": cenario, "run_id": run_id, "rep": rep, "pc": pc,
                       "offset_inicio_ms": valores["inicio"], "offset_fim_ms": valores["fim"]})
    return linhas
 
 
def offsets_da_rep(linhas_offset, cenario, run_id, rep):
    """Offset de cada PC na repeticao = media de inicio e fim (ms). Avisa se faltar ou se derivar."""
    por_pc = {}
    for o in linhas_offset:
        ini, fim = o["offset_inicio_ms"], o["offset_fim_ms"]
        valores = [v for v in (ini, fim) if not np.isnan(v)]
        por_pc[o["pc"]] = float(np.mean(valores)) if valores else np.nan
        if not valores:
            aviso(f"{cenario}/{run_id}/rep{rep}: sem offset de {o['pc']}; latencia corrigida fica vazia")
        elif len(valores) == 2 and abs(ini - fim) > LIMITE_DERIVA_MS:
            aviso(f"{cenario}/{run_id}/rep{rep}: offset de {o['pc']} variou {abs(ini - fim):.1f} ms "
                  f"entre inicio e fim ({ini:.1f} -> {fim:.1f}); a correcao usa a media")
    return por_pc
 
 
# ---------------------------------------------------------------- calculo
 
def percentil(v, q):
    return float(np.percentile(v, q)) if len(v) else np.nan
 
 
def analisar_rep(cenario, run_id, rep, d, warmup_s, offsets):
    """Devolve (linhas de metricas por assinatura, amostras de latencia, info de publicacao).
    offsets: {pc: offset em ms (local - referencia)}, usado nas metricas _corr."""
    pub = pd.read_csv(d / "pc-a.csv")
    if pub.empty:
        aviso(f"{d / 'pc-a.csv'} vazio; ignorado")
        return [], [], None
    t0 = pub["ts_publicacao"].min()
    pub["t_rel"] = (pub["ts_publicacao"] - t0) / 1000.0
    janela = pub[pub["t_rel"] >= warmup_s]
 
    def taxa(df):
        span = (df["ts_publicacao"].max() - df["ts_publicacao"].min()) / 1000.0
        return (len(df) - 1) / span if len(df) > 1 and span > 0 else np.nan
 
    info_pub = {"cenario": cenario, "run_id": run_id, "rep": rep,
                "publicadas_total": len(pub), "taxa_real": taxa(pub),
                "publicadas_janela": len(janela), "taxa_real_janela": taxa(janela)}
 
    off_a = offsets.get("pc-a", np.nan)
    if np.isnan(off_a):
        aviso(f"{cenario}/{run_id}/rep{rep}: sem offset do pc-a; latencia corrigida fica vazia")
    ref = pub[["seq", "topico", "ts_publicacao", "t_rel"]].rename(
        columns={"topico": "topico_pub", "ts_publicacao": "ts_pub_a"})
    linhas, amostras = [], []
 
    for pc, assinaturas in PCS.items():
        arq = d / f"{pc}.csv"
        if not arq.exists():
            aviso(f"{arq} nao encontrado; {pc} fica fora de {cenario}/{run_id}/rep{rep}")
            continue
        rec = pd.read_csv(arq)
        for s in assinaturas:
            topico = ASSINATURAS[s]
            r = rec[rec["assinatura"] == s].merge(ref, on="seq", how="left")
            desconhecidas = int((r["topico_pub"].isna() | (r["topico_pub"] != topico)).sum())
            esperadas = set(janela.loc[janela["topico"] == topico, "seq"])
            rv = r[r["seq"].isin(esperadas) & (r["topico_pub"] == topico)]
            primeira = rv.sort_values("ts_recebimento").drop_duplicates("seq")
            lat = (primeira["ts_recebimento"] - primeira["ts_pub_a"]).to_numpy()
            off_c = offsets.get(pc, np.nan)
            lat_corr = lat - off_c + off_a              # NaN se faltar algum offset
            a_nuvem = primeira["publish_time_servidor"] - primeira["ts_pub_a"]
            nuvem_pc = primeira["ts_recebimento"] - primeira["publish_time_servidor"]
            span = (primeira["ts_recebimento"].max() - primeira["ts_recebimento"].min()) / 1000.0
            n = len(primeira)
            linhas.append({
                "cenario": cenario, "run_id": run_id, "rep": rep, "pc": pc, "assinatura": s, "topico": topico,
                "publicadas": len(esperadas),
                "recebidas": n,
                "perdas": len(esperadas) - n,
                "perdas_pct": 100.0 * (len(esperadas) - n) / len(esperadas) if esperadas else np.nan,
                "duplicatas": len(rv) - n,
                "desconhecidas": desconhecidas,
                "vazao": (n - 1) / span if n > 1 and span > 0 else np.nan,
                "lat_media": float(np.mean(lat)) if n else np.nan,
                "lat_p50": percentil(lat, 50),
                "lat_p95": percentil(lat, 95),
                "lat_p99": percentil(lat, 99),
                "a_nuvem_p50": float(a_nuvem.median()),
                "nuvem_pc_p50": float(nuvem_pc.median()),
                "offset_pc_a_ms": off_a,
                "offset_consumidor_ms": off_c,
                "lat_media_corr": float(np.mean(lat_corr)) if n else np.nan,
                "lat_p50_corr": percentil(lat_corr, 50),
                "lat_p95_corr": percentil(lat_corr, 95),
                "lat_p99_corr": percentil(lat_corr, 99),
                "a_nuvem_p50_corr": float(a_nuvem.median()) + off_a,
                "nuvem_pc_p50_corr": float(nuvem_pc.median()) - off_c,
            })
            amostras.append(pd.DataFrame({
                "cenario": cenario, "run_id": run_id, "rep": rep, "pc": pc, "assinatura": s,
                "t_rel": primeira["t_rel"].to_numpy(), "latencia": lat, "latencia_corr": lat_corr,
            }))
    return linhas, amostras, info_pub
 
 
def agregar(por_rep):
    chaves = ["cenario", "run_id", "pc", "assinatura", "topico"]
    cols = [c for c, _, _ in METRICAS + METRICAS_CORR]
    g = por_rep.groupby(chaves, sort=True)
    media = g[cols].mean().add_suffix("_media")
    desvio = g[cols].std(ddof=1).add_suffix("_desvio")   # NaN com uma repeticao so
    agg = pd.concat([g.size().rename("reps"), media, desvio], axis=1).reset_index()
    ordem = ["cenario", "run_id", "pc", "assinatura", "topico", "reps"]
    for c in cols:
        ordem += [f"{c}_media", f"{c}_desvio"]
    return agg[ordem]
 
 
# ---------------------------------------------------------------- saida: tabela.md
 
def fmt(media, desvio, casas):
    if pd.isna(media):
        return "-"
    s = f"{media:.{casas}f}"
    return s if pd.isna(desvio) else f"{s} ± {desvio:.{casas}f}"
 
 
def tabela_md(agg, pubs, offsets, warmup_s):
    out = ["# Resultados", "",
           f"Warm-up descartado: {warmup_s:g} s iniciais de cada repeticao. "
           "Valores: media ± desvio padrao entre repeticoes. "
           "Latencia = ts_recebimento − ts_publicacao (primeira entrega de cada seq).", ""]
    for (cenario, run_id), bloco in agg.groupby(["cenario", "run_id"], sort=True):
        out += [f"## {cenario} / {run_id}", ""]
        p = pubs[(pubs["cenario"] == cenario) & (pubs["run_id"] == run_id)]
        if not p.empty:
            out.append(f"Taxa real publicada (PC A, rodada inteira): "
                       f"{fmt(p['taxa_real'].mean(), p['taxa_real'].std(ddof=1), 3)} msgs/s "
                       f"em {len(p)} repeticao(oes); {int(p['publicadas_total'].sum())} mensagens no total.")
            out.append("")
        cab = ["PC", "Assinatura", "Reps"] + [rot for _, rot, _ in METRICAS]
        out.append("| " + " | ".join(cab) + " |")
        out.append("|" + "|".join(["---"] * 3 + ["---:"] * len(METRICAS)) + "|")
        for _, r in bloco.iterrows():
            cel = [r["pc"], r["assinatura"], str(int(r["reps"]))]
            cel += [fmt(r[f"{c}_media"], r[f"{c}_desvio"], casas) for c, _, casas in METRICAS]
            out.append("| " + " | ".join(cel) + " |")
        out.append("")
        out += ["Latencias corrigidas pelo offset do relogio "
                "(latencia − offset do consumidor + offset do PC A; offset = media de inicio e fim da repeticao):",
                ""]
        cab = ["PC", "Assinatura", "Reps"] + [rot for _, rot, _ in METRICAS_CORR]
        out.append("| " + " | ".join(cab) + " |")
        out.append("|" + "|".join(["---"] * 3 + ["---:"] * len(METRICAS_CORR)) + "|")
        for _, r in bloco.iterrows():
            cel = [r["pc"], r["assinatura"], str(int(r["reps"]))]
            cel += [fmt(r[f"{c}_media"], r[f"{c}_desvio"], casas) for c, _, casas in METRICAS_CORR]
            out.append("| " + " | ".join(cel) + " |")
        out.append("")
        o = offsets[(offsets["cenario"] == cenario) & (offsets["run_id"] == run_id)] if not offsets.empty else offsets
        if not o.empty:
            out += ["Offset do relogio (local − time.google.com, ms; positivo = local adiantado), "
                    "considerando as medicoes de inicio e fim de todas as repeticoes:", "",
                    "| PC | Min | Max | Media |", "|---|---:|---:|---:|"]
            vals = o.melt(id_vars=["pc"], value_vars=["offset_inicio_ms", "offset_fim_ms"])
            for pc, v in vals.groupby("pc", sort=True)["value"]:
                if v.notna().any():
                    out.append(f"| {pc} | {v.min():.1f} | {v.max():.1f} | {v.mean():.1f} |")
                else:
                    out.append(f"| {pc} | - | - | - |")
            out.append("")
    return "\n".join(out)
 
 
# ---------------------------------------------------------------- graficos
 
def estilo_eixos(ax):
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(COR_SECUNDARIA)
    ax.tick_params(colors=COR_SECUNDARIA, labelcolor=COR_TEXTO)
    ax.grid(True, color=COR_GRADE, linewidth=0.8)
    ax.set_axisbelow(True)
 
 
def rotulo(s):
    return f"{s} ({ASSINATURAS[s]})"
 
 
def grafico_cdf(lat, titulo, arquivo, assinaturas=None, rotulo_x="Latencia (ms, escala log)"):
    assinaturas = assinaturas or [s for s in ESTILO if s in set(lat["assinatura"])]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    for s in assinaturas:
        v = lat.loc[lat["assinatura"] == s, "latencia"].to_numpy()
        v = np.sort(v[v > 0])   # escala log: descarta <= 0 (possivel na latencia corrigida)
        if len(v) == 0:
            continue
        y = np.arange(1, len(v) + 1) / len(v)
        ax.plot(v, y, linewidth=2, label=f"{rotulo(s)}  n={len(v)}", **ESTILO[s])
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}"))
    ax.xaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(
        lambda x, _: f"{x:g}" if f"{x:g}"[0] in "25" else ""))
    ax.set_xlabel(rotulo_x, color=COR_TEXTO)
    ax.set_ylabel("Fracao das mensagens", color=COR_TEXTO)
    ax.set_ylim(0, 1.01)
    for q in (0.5, 0.95, 0.99):
        ax.axhline(q, color=COR_SECUNDARIA, linewidth=0.6, linestyle=(0, (2, 3)))
        ax.annotate(f"p{int(q * 100)}", xy=(1.0, q), xycoords=("axes fraction", "data"),
                    xytext=(3, 0), textcoords="offset points", va="center", fontsize=8, color=COR_SECUNDARIA)
    estilo_eixos(ax)
    ax.set_title(titulo, color=COR_TEXTO, loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(arquivo, dpi=200)
    plt.close(fig)
 
 
def grafico_tempo(lat, titulo, arquivo):
    assinaturas = [s for s in ESTILO if s in set(lat["assinatura"])]
    if not assinaturas:
        return
    fig, eixos = plt.subplots(len(assinaturas), 1, figsize=(7, 1.9 * len(assinaturas) + 0.6),
                              sharex=True, squeeze=False)
    for ax, s in zip(eixos[:, 0], assinaturas):
        d = lat[lat["assinatura"] == s].copy()
        d["seg"] = np.floor(d["t_rel"]).astype(int)
        por_seg = d.groupby("seg")["latencia"]
        p50, p95 = por_seg.median(), por_seg.quantile(0.95)
        # cada painel ja identifica a assinatura: linha cheia = p50, tracejada clara = p95
        ax.plot(p50.index, p50.to_numpy(), linewidth=2, color=ESTILO[s]["color"], label="p50 por segundo")
        ax.plot(p95.index, p95.to_numpy(), linewidth=1.2, color=ESTILO[s]["color"], alpha=0.55,
                linestyle="--", label="p95 por segundo")
        ax.set_ylabel("ms", color=COR_TEXTO)
        ax.set_ylim(bottom=0)
        ax.set_title(rotulo(s), color=COR_TEXTO, loc="left", fontsize=9)
        estilo_eixos(ax)
    eixos[-1, 0].set_xlabel("Tempo desde o inicio da publicacao (s), repeticoes juntas", color=COR_TEXTO)
    fig.suptitle(titulo, color=COR_TEXTO, x=0.02, ha="left", fontsize=11)
    # legenda vale para todos os paineis: em cinza neutro, nao na cor de um deles
    alcas = [matplotlib.lines.Line2D([], [], color=COR_SECUNDARIA, linewidth=2),
             matplotlib.lines.Line2D([], [], color=COR_SECUNDARIA, linewidth=1.2, alpha=0.55, linestyle="--")]
    fig.legend(alcas, ["p50 por segundo", "p95 por segundo"], frameon=False, fontsize=8,
               loc="upper right", ncol=2)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(arquivo, dpi=200)
    plt.close(fig)
 
 
# ---------------------------------------------------------------- main
 
def main():
    p = argparse.ArgumentParser(description="Analisa as rodadas e gera tabelas e graficos.")
    p.add_argument("dados", help="pasta com <cenario>/<run_id>/rep<N>/ (ex.: IoT_setup/dados)")
    p.add_argument("--warmup", type=float, default=10.0, help="segundos iniciais descartados (padrao: 10)")
    p.add_argument("--saida", default=str(RAIZ / "resultados"), help="pasta de saida (padrao: IoT_setup/resultados)")
    p.add_argument("--sem-correcao", action="store_true",
                   help="graficos com a latencia bruta, sem corrigir pelo offset do relogio")
    args = p.parse_args()
 
    raiz = Path(args.dados)
    if not raiz.is_dir():
        sys.exit(f"Erro: {raiz} nao e uma pasta")
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
 
    reps = descobrir_reps(raiz)
    if not reps:
        sys.exit(f"Erro: nenhuma pasta rep<N> com pc-a.csv em {raiz}")
 
    linhas, amostras, pubs, offsets = [], [], [], []
    for cenario, run_id, rep, d in reps:
        off_rep = ler_offsets(d, cenario, run_id, rep)
        offsets += off_rep
        l, a, info = analisar_rep(cenario, run_id, rep, d, args.warmup,
                                  offsets_da_rep(off_rep, cenario, run_id, rep))
        linhas += l
        amostras += a
        if info:
            pubs.append(info)
 
    if not linhas:
        sys.exit("Erro: nenhum CSV de consumidor (pc-b/c/d.csv) encontrado junto dos pc-a.csv")
 
    por_rep = pd.DataFrame(linhas)
    pubs = pd.DataFrame(pubs)
    offsets = pd.DataFrame(offsets)
    lat = pd.concat(amostras, ignore_index=True)
    if args.sem_correcao:
        rotulo_x = "Latencia bruta ts_recebimento − ts_publicacao (ms, escala log)"
    else:
        # graficos usam a corrigida; a bruta segue nas tabelas
        lat["latencia"] = lat["latencia_corr"]
        rotulo_x = "Latencia corrigida pelo offset do relogio (ms, escala log)"
        if lat["latencia"].isna().all():
            aviso("nenhuma latencia corrigida (offsets ausentes); use --sem-correcao")
    agg = agregar(por_rep)
 
    por_rep.to_csv(saida / "tabela_reps.csv", index=False)
    agg.to_csv(saida / "tabela.csv", index=False)
    pubs.to_csv(saida / "publicacao.csv", index=False)
    if not offsets.empty:
        offsets.to_csv(saida / "offsets.csv", index=False)
    (saida / "tabela.md").write_text(tabela_md(agg, pubs, offsets, args.warmup), encoding="utf-8")
 
    if (por_rep["desconhecidas"] > 0).any():
        aviso("ha mensagens recebidas cujo seq/topico nao aparece no pc-a.csv (ver coluna desconhecidas em tabela_reps.csv)")
 
    graficos = []
    for (cenario, run_id), l in lat.groupby(["cenario", "run_id"], sort=True):
        base = f"{cenario}_{run_id}"
        n_reps = l["rep"].nunique()
        sufixo = f"{cenario} / {run_id} ({n_reps} rep.)"
        graficos.append(saida / f"cdf_latencia_{base}.png")
        grafico_cdf(l, f"CDF da latencia por assinatura · {sufixo}", graficos[-1], rotulo_x=rotulo_x)
        graficos.append(saida / f"latencia_tempo_{base}.png")
        grafico_tempo(l, f"Latencia ao longo do tempo · {sufixo}", graficos[-1])
        if {"sub-c-gases", "sub-d-gases"} <= set(l["assinatura"]):
            graficos.append(saida / f"gases_c_vs_d_{base}.png")
            grafico_cdf(l, f"Topico gases: PC C (2,4 GHz) × PC D (5 GHz) · {sufixo}", graficos[-1],
                        ["sub-c-gases", "sub-d-gases"], rotulo_x=rotulo_x)
 
    print(f"{len(reps)} repeticao(oes) analisada(s); resultados em {saida}:")
    for f in ["tabela.md", "tabela.csv", "tabela_reps.csv", "publicacao.csv"] + \
             (["offsets.csv"] if not offsets.empty else []):
        print(f"  {f}")
    for g in graficos:
        print(f"  {g.name}")
 
 
if __name__ == "__main__":
    main()