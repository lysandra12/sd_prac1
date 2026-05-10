import matplotlib.pyplot as plt
import numpy as np

# ============================================================
#  DATOS
# ============================================================

datos = {
    # --- DIRECT ---
    "direct_unnumbered_1w":  {"throughput": 328.72, "success": 20000, "fail": 0,    "elapsed": 60.842,
                               "workers": [{"id":1,"throughput":328.76,"success":20000,"fail":0}]},
    "direct_numbered_1w":    {"throughput": 269.09, "success": 20000, "fail": 5997, "elapsed": 96.612,
                               "workers": [{"id":1,"throughput":269.12,"success":20000,"fail":5997}]},

    "direct_unnumbered_2w":  {"throughput": 287.97, "success": 20000, "fail": 0, "elapsed": 69.452,
                               "workers": [{"id":1,"throughput":144.01,"success":10000,"fail":0},
                                           {"id":2,"throughput":144.02,"success":10000,"fail":0}]},
    "direct_numbered_2w":    {"throughput": 251.14, "success": 20000, "fail": 5997, "elapsed": 103.517,
                               "workers": [{"id":1,"throughput":125.58,"success":10002,"fail":2997},
                                           {"id":2,"throughput":125.58,"success":9998, "fail":3000}]},

    "direct_unnumbered_3w":  {"throughput": 286.10, "success": 20000, "fail": 0, "elapsed": 69.906,
                               "workers": [{"id":1,"throughput":95.39,"success":6667,"fail":0},
                                           {"id":2,"throughput":95.39,"success":6667,"fail":0},
                                           {"id":3,"throughput":95.40,"success":6666,"fail":0}]},
    "direct_numbered_3w":    {"throughput": 238.08, "success": 20000, "fail": 5997, "elapsed": 109.195,
                               "workers": [{"id":1,"throughput":79.37,"success":6667,"fail":1999},
                                           {"id":2,"throughput":79.37,"success":6667,"fail":1999},
                                           {"id":3,"throughput":79.37,"success":6666,"fail":1999}]},

    "direct_unnumbered_6w":  {"throughput": 279.56, "success": 20000, "fail": 0, "elapsed": 71.542,
                               "workers": [{"id":1,"throughput":46.61,"success":3334,"fail":0},
                                           {"id":2,"throughput":46.61,"success":3334,"fail":0},
                                           {"id":3,"throughput":46.61,"success":3333,"fail":0},
                                           {"id":4,"throughput":46.61,"success":3333,"fail":0},
                                           {"id":5,"throughput":46.61,"success":3333,"fail":0},
                                           {"id":6,"throughput":46.62,"success":3333,"fail":0}]},
    "direct_numbered_6w":    {"throughput": 248.61, "success": 20000, "fail": 5997, "elapsed": 104.571,
                               "workers": [{"id":1,"throughput":41.44,"success":3334,"fail":999},
                                           {"id":2,"throughput":41.45,"success":3333,"fail":1000},
                                           {"id":3,"throughput":41.45,"success":3334,"fail":999},
                                           {"id":4,"throughput":41.45,"success":3334,"fail":999},
                                           {"id":5,"throughput":41.45,"success":3333,"fail":1000},
                                           {"id":6,"throughput":41.45,"success":3332,"fail":1000}]},

    # --- INDIRECT ---
    "indirect_unnumbered_1w":  {"throughput": 681.14, "success": 20000, "fail": 0,    "elapsed": 29.36,
                               "workers": [{"id":1,"throughput":681.14,"success":20000,"fail":0}]},
    "indirect_numbered_1w":    {"throughput": 517.40, "success": 20000, "fail": 5997, "elapsed": 50.25,
                               "workers": [{"id":1,"throughput":517.40,"success":20000,"fail":5997}]},

    "indirect_unnumbered_2w":  {"throughput": 1327.51, "success": 20000, "fail": 0,    "elapsed": 15.07,
                               "workers": [{"id":1,"throughput":637.46,"success":9604, "fail":0},
                                           {"id":2,"throughput":690.05,"success":10396,"fail":0}]},
    "indirect_numbered_2w":    {"throughput": 1074.17, "success": 20000, "fail": 5997, "elapsed": 24.20,
                               "workers": [{"id":1,"throughput":519.35,"success":9624, "fail":2945},
                                           {"id":2,"throughput":554.82,"success":10376,"fail":3052}]},

    "indirect_unnumbered_3w":  {"throughput": 1867.35, "success": 20000, "fail": 0, "elapsed": 10.71,
                               "workers": [{"id":1,"throughput":609.30,"success":6526,"fail":0},
                                           {"id":2,"throughput":646.69,"success":6926,"fail":0},
                                           {"id":3,"throughput":611.36,"success":6548,"fail":0}]},
    "indirect_numbered_3w":    {"throughput": 1492.70, "success": 20000, "fail": 5997, "elapsed": 17.41,
                               "workers": [{"id":1,"throughput":481.65,"success":6445,"fail":1944},
                                           {"id":2,"throughput":523.73,"success":7014,"fail":2107},
                                           {"id":3,"throughput":487.32,"success":6541,"fail":1946}]},

    "indirect_unnumbered_6w":  {"throughput": 2584.90, "success": 20000, "fail": 0, "elapsed": 7.74,
                               "workers": [{"id":1,"throughput":413.56,"success":3200,"fail":0},
                                           {"id":2,"throughput":444.25,"success":3438,"fail":0},
                                           {"id":3,"throughput":416.44,"success":3222,"fail":0},
                                           {"id":4,"throughput":431.94,"success":3342,"fail":0},
                                           {"id":5,"throughput":425.28,"success":3290,"fail":0},
                                           {"id":6,"throughput":453.43,"success":3508,"fail":0}]},
    "indirect_numbered_6w":    {"throughput": 2226.34, "success": 20000, "fail": 5997, "elapsed": 11.67,
                               "workers": [{"id":1,"throughput":357.77,"success":3200,"fail":978},
                                           {"id":2,"throughput":372.84,"success":3347,"fail":1007},
                                           {"id":3,"throughput":365.07,"success":3273,"fail":990},
                                           {"id":4,"throughput":362.17,"success":3249,"fail":980},
                                           {"id":5,"throughput":372.46,"success":3356,"fail":993},
                                           {"id":6,"throughput":396.03,"success":3575,"fail":1049}]},
}

WORKERS = [1, 2, 3, 6]

def tp(arch, modo, nw):
    return datos.get(f"{arch}_{modo}_{nw}w", {}).get("throughput", 0)


# ============================================================
#  GRÁFICA 1 — Throughput vs número de workers (4 líneas)
# ============================================================

def grafica_throughput_vs_workers():
    fig, ax = plt.subplots(figsize=(9, 5))

    series = {
        "Direct — Unnumbered":   ("direct",   "unnumbered", "#1f77b4", "o-"),
        "Direct — Numbered":     ("direct",   "numbered",   "#1f77b4", "o--"),
        "Indirect — Unnumbered": ("indirect", "unnumbered", "#ff7f0e", "s-"),
        "Indirect — Numbered":   ("indirect", "numbered",   "#ff7f0e", "s--"),
    }

    for label, (arch, modo, color, fmt) in series.items():
        vals = [tp(arch, modo, nw) for nw in WORKERS]
        ax.plot(WORKERS, vals, fmt, color=color, linewidth=2, markersize=8, label=label)
        for nw, v in zip(WORKERS, vals):
            ax.annotate(f"{v:.0f}", (nw, v), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=8)

    ax.set_xlabel("Número de workers", fontsize=12)
    ax.set_ylabel("Throughput (ops/s)", fontsize=12)
    ax.set_title("Throughput vs. Número de Workers", fontsize=13, fontweight="bold")
    ax.set_xticks(WORKERS)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig("grafica_throughput_vs_workers.png", dpi=150)
    print("Guardada: grafica_throughput_vs_workers.png")
    plt.show()


# ============================================================
#  GRÁFICA 2 — Direct vs Indirect (barras agrupadas)
# ============================================================

def grafica_direct_vs_indirect():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)

    for ax, modo in zip(axes, ["unnumbered", "numbered"]):
        x      = np.arange(len(WORKERS))
        ancho  = 0.35
        d_vals = [tp("direct",   modo, nw) for nw in WORKERS]
        i_vals = [tp("indirect", modo, nw) for nw in WORKERS]

        bars_d = ax.bar(x - ancho/2, d_vals, ancho, label="Direct (Pyro5)",      color="#1f77b4", edgecolor="white")
        bars_i = ax.bar(x + ancho/2, i_vals, ancho, label="Indirect (RabbitMQ)", color="#ff7f0e", edgecolor="white")

        for bar, val in list(zip(bars_d, d_vals)) + list(zip(bars_i, i_vals)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10,
                    f"{val:.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_title(f"{'Unnumbered' if modo == 'unnumbered' else 'Numbered'}", fontsize=12)
        ax.set_xlabel("Número de workers")
        ax.set_ylabel("Throughput (ops/s)")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{nw}w" for nw in WORKERS])
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Direct vs. Indirect — Comparativa de Throughput", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("grafica_direct_vs_indirect.png", dpi=150)
    print("Guardada: grafica_direct_vs_indirect.png")
    plt.show()


# ============================================================
#  GRÁFICA 3 — Numbered vs Unnumbered (barras agrupadas)
# ============================================================

def grafica_numbered_vs_unnumbered():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)

    for ax, arch in zip(axes, ["direct", "indirect"]):
        x      = np.arange(len(WORKERS))
        ancho  = 0.35
        u_vals = [tp(arch, "unnumbered", nw) for nw in WORKERS]
        n_vals = [tp(arch, "numbered",   nw) for nw in WORKERS]

        bars_u = ax.bar(x - ancho/2, u_vals, ancho, label="Unnumbered", color="#2ca02c", edgecolor="white")
        bars_n = ax.bar(x + ancho/2, n_vals, ancho, label="Numbered",   color="#d62728", edgecolor="white")

        for bar, val in list(zip(bars_u, u_vals)) + list(zip(bars_n, n_vals)):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 10,
                    f"{val:.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_title(f"{'Direct (Pyro5)' if arch == 'direct' else 'Indirect (RabbitMQ)'}", fontsize=12)
        ax.set_xlabel("Número de workers")
        ax.set_ylabel("Throughput (ops/s)")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{nw}w" for nw in WORKERS])
        ax.legend()
        ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Numbered vs. Unnumbered — Comparativa de Throughput", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("grafica_numbered_vs_unnumbered.png", dpi=150)
    print("Guardada: grafica_numbered_vs_unnumbered.png")
    plt.show()


# ============================================================
#  EJECUTAR
# ============================================================

if __name__ == "__main__":
    grafica_throughput_vs_workers()
    grafica_direct_vs_indirect()
    grafica_numbered_vs_unnumbered()
