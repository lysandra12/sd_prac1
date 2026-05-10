import matplotlib.pyplot as plt
import numpy as np

# ============================================================
#  DATOS — rellena con tus resultados
# ============================================================

datos = {
    # --- DIRECT ---
    # --- DIRECT ---
    "direct_unnumbered_1w":  {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
    "direct_numbered_1w":    {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},

    "direct_unnumbered_2w":  {"throughput": 346.16, "success": 14395, "fail": 0,    "elapsed": 41.585,
                               "workers": [{"id":1,"throughput":173.14,"success":7198,"fail":0},
                                           {"id":2,"throughput":173.13,"success":7198,"fail":0}]},
    "direct_numbered_2w":    {"throughput": 289.53, "success": 20000, "fail": 5997, "elapsed": 89.789,
                               "workers": [{"id":1,"throughput":144.79,"success":9998,"fail":3000},
                                           {"id":2,"throughput":144.78,"success":10002,"fail":2997}]},

    "direct_unnumbered_3w":  {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
    "direct_numbered_3w":    {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},

    "direct_unnumbered_6w":  {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
    "direct_numbered_6w":    {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},

    # --- INDIRECT ---
    "indirect_unnumbered_1w":  {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
    "indirect_numbered_1w":    {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},

    "indirect_unnumbered_2w":  {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
    "indirect_numbered_2w":    {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},

    "indirect_unnumbered_3w":  {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
    "indirect_numbered_3w":    {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},

    "indirect_unnumbered_6w":  {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
    "indirect_numbered_6w":    {"throughput": 0, "success": 0, "fail": 0, "elapsed": 0, "workers": []},
}

WORKERS = [1, 2, 3, 6]
MODOS   = ["unnumbered", "numbered"]
ARCHS   = ["direct", "indirect"]

# ============================================================
#  HELPERS
# ============================================================

def get(arch, modo, nw):
    return datos.get(f"{arch}_{modo}_{nw}w", {})

def valores_escalabilidad(arch, modo):
    nws = []; tps = []
    for nw in WORKERS:
        d = get(arch, modo, nw)
        if d.get("throughput", 0) > 0:
            nws.append(nw); tps.append(d["throughput"])
    return nws, tps


# ============================================================
#  GRÁFICA 1 — Throughput: Direct vs Indirect (por modo y nº workers)
# ============================================================

def grafica_throughput_comparativa():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=False)

    for ax, modo in zip(axes, MODOS):
        x      = np.arange(len(WORKERS))
        ancho  = 0.35
        d_vals = [get("direct",   modo, nw).get("throughput", 0) for nw in WORKERS]
        i_vals = [get("indirect", modo, nw).get("throughput", 0) for nw in WORKERS]

        bars_d = ax.bar(x - ancho/2, d_vals, ancho, label="Direct (Pyro5)",    color="#4C72B0", edgecolor="white")
        bars_i = ax.bar(x + ancho/2, i_vals, ancho, label="Indirect (RabbitMQ)", color="#DD8452", edgecolor="white")

        for bar, val in list(zip(bars_d, d_vals)) + list(zip(bars_i, i_vals)):
            if val > 0:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                        f"{val:.0f}", ha="center", va="bottom", fontsize=8, fontweight="bold")

        ax.set_title(f"Throughput — {modo.capitalize()}")
        ax.set_xlabel("Número de workers")
        ax.set_ylabel("Throughput (ops/s)")
        ax.set_xticks(x); ax.set_xticklabels(WORKERS)
        ax.legend(); ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Comparativa de throughput: Direct vs Indirect", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("grafica_throughput.png", dpi=150)
    print("Guardada: grafica_throughput.png")
    plt.show()


# ============================================================
#  GRÁFICA 2 — Éxitos vs Fallos
# ============================================================

def grafica_exitos_fallos():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))

    for ax, modo in zip(axes, MODOS):
        etiquetas = [f"{a}\n{nw}w" for a in ARCHS for nw in WORKERS]
        exitos    = [get(a, modo, nw).get("success", 0) for a in ARCHS for nw in WORKERS]
        fallos    = [get(a, modo, nw).get("fail",    0) for a in ARCHS for nw in WORKERS]

        x = np.arange(len(etiquetas)); ancho = 0.35
        ax.bar(x - ancho/2, exitos, ancho, label="Éxitos",  color="#55A868", edgecolor="white")
        ax.bar(x + ancho/2, fallos, ancho, label="Fallos",  color="#C44E52", edgecolor="white")

        ax.set_title(f"Éxitos vs Fallos — {modo.capitalize()}")
        ax.set_xlabel("Configuración"); ax.set_ylabel("Peticiones")
        ax.set_xticks(x); ax.set_xticklabels(etiquetas, fontsize=8)
        ax.legend(); ax.grid(axis="y", alpha=0.3)

    plt.suptitle("Éxitos vs Fallos por configuración", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("grafica_exitos_fallos.png", dpi=150)
    print("Guardada: grafica_exitos_fallos.png")
    plt.show()


# ============================================================
#  GRÁFICA 3 — Escalabilidad (throughput vs nº workers)
# ============================================================

def grafica_escalabilidad():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    colores = {"direct": "#4C72B0", "indirect": "#DD8452"}

    for ax, modo in zip(axes, MODOS):
        for arch in ARCHS:
            nws, tps = valores_escalabilidad(arch, modo)
            if len(nws) < 1:
                continue
            ax.plot(nws, tps, "o-", color=colores[arch], linewidth=2,
                    markersize=8, label=arch.capitalize())

            # Escalado lineal ideal desde el primer punto
            if tps:
                ideal = [tps[0] * (n / nws[0]) for n in nws]
                ax.plot(nws, ideal, "--", color=colores[arch], linewidth=1,
                        alpha=0.4, label=f"{arch.capitalize()} ideal")

        ax.set_title(f"Escalabilidad — {modo.capitalize()}")
        ax.set_xlabel("Número de workers"); ax.set_ylabel("Throughput (ops/s)")
        ax.set_xticks(WORKERS); ax.legend(); ax.grid(alpha=0.3)

    plt.suptitle("Escalabilidad: throughput vs número de workers", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("grafica_escalabilidad.png", dpi=150)
    print("Guardada: grafica_escalabilidad.png")
    plt.show()


# ============================================================
#  GRÁFICA 4 — Distribución de carga entre workers
# ============================================================

def grafica_carga_workers():
    # Muestra la distribución para cada configuración que tenga datos de workers
    claves_con_workers = [(k, v) for k, v in datos.items() if v.get("workers")]
    if not claves_con_workers:
        print("Sin datos de workers detallados")
        return

    n = len(claves_con_workers)
    fig, axes = plt.subplots(1, n, figsize=(5 * n, 4))
    if n == 1:
        axes = [axes]

    for ax, (clave, entrada) in zip(axes, claves_con_workers):
        workers     = entrada["workers"]
        ids         = [f"W{w['id']}" for w in workers]
        throughputs = [w["throughput"] for w in workers]
        colores     = plt.cm.Blues(np.linspace(0.4, 0.85, len(workers)))

        ax.bar(ids, throughputs, color=colores, edgecolor="white")
        media = entrada["throughput"] / len(workers)
        ax.axhline(y=media, color="red", linestyle="--", alpha=0.7, label=f"Media: {media:.0f}")

        for i, val in enumerate(throughputs):
            ax.text(i, val + 0.5, f"{val:.0f}", ha="center", va="bottom", fontsize=9)

        ax.set_title(clave.replace("_", "\n"), fontsize=9)
        ax.set_ylabel("ops/s"); ax.legend(fontsize=8)

    plt.suptitle("Distribución de carga entre workers", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig("grafica_carga_workers.png", dpi=150)
    print("Guardada: grafica_carga_workers.png")
    plt.show()


# ============================================================
#  EJECUTAR
# ============================================================

if __name__ == "__main__":
    grafica_throughput_comparativa()
    grafica_exitos_fallos()
    grafica_escalabilidad()
    grafica_carga_workers()
