import argparse
import csv
import os
from collections import deque

import matplotlib.pyplot as plt

REPRESENTATIONS = [
    {"quality": "240p", "bitrate_kbps": 200},
    {"quality": "360p", "bitrate_kbps": 400},
    {"quality": "480p", "bitrate_kbps": 700},
]

FIELDNAMES = [
    "segment",
    "timestamp",
    "server_id",
    "quality",
    "bitrate_kbps",
    "vazao_kbps",
    "download_time_s",
    "variacao de atraso (jitter)_network_ms",
    "variacao de atraso (jitter)_ewma_ms",
    "buffer_level_s",
    "buffer_can_play",
    "rebuffer_event",
    "stall_duration_s",
    "failover_total",
]

# TODO copiado do main
POLICY_NAMES = {
    "1": "Rate-Based (baseline)",
    "2": "Buffer-Based",
    "3": "Hibrida EWMA + desvio padrao + penalidade de jitter",
}

def load_trace(path):
    with open(path, newline="", encoding="utf-8") as csvfile:
        rows = list(csv.DictReader(csvfile))

    trace = []
    for row in rows:
        trace.append(
            {
                "segment": int(row["segment"]),
                "timestamp": row["timestamp"],
                "server_id": row.get("server_id", "A"),
                "throughput_kbps": float(row["vazao_kbps"]),
                "jitter_network_ms": float(row["variacao de atraso (jitter)_network_ms"]),
                "jitter_ewma_ms": float(row["variacao de atraso (jitter)_ewma_ms"]),
                "failover_total": int(float(row.get("failover_total", 0))),
            }
        )
    return trace

def estimate_segment_duration(input_csv):
    with open(input_csv, newline="", encoding="utf-8") as csvfile:
        first_row = next(csv.DictReader(csvfile), None)

    if not first_row:
        return 2.0

    first_buffer = float(first_row["buffer_level_s"])
    return first_buffer if first_buffer > 0 else 2.0

def select_rate_based(representations, throughput_history, safety_factor=0.85):
    if not throughput_history:
        return representations[0]

    avg_throughput = sum(throughput_history) / len(throughput_history)
    safe_throughput = avg_throughput * safety_factor

    selected = representations[0]
    for representation in representations:
        if representation["bitrate_kbps"] > safe_throughput:
            break
        selected = representation
    return selected

def select_buffer_based(representations, buffer_level_s): # Escolhe qualidade de acordo com o nível do buffer
    if buffer_level_s < 4.0: # TODO: Escolhe a qualidade de acondo com a disbonibilidade do buffer
        return representations[0] # Menor qualidade
    elif buffer_level_s < 8.0:
        return representations[min(1, len(representations) - 1)]
    return representations[-1] # Maior qualidae

def update_ewma(previous_ewma, new_sample, alpha=0.3):
    if previous_ewma is None:
        return new_sample
    return alpha * new_sample + (1 - alpha) * previous_ewma

def rolling_std(history):
    n = len(history)
    if n < 2:
        return 0.0
    mean = sum(history) / n
    variance = sum((x - mean) ** 2 for x in history) / n
    return variance ** 0.5

def select_hybrid(
    representations,
    ewma_throughput,
    std_throughput,
    jitter_ewma_ms,
    buffer_level_s,
    k_std=1.0,
    jitter_ref_ms=80.0,
    jitter_penalty_max=0.4,
    buffer_boost_threshold=10.0,
    buffer_boost_factor=1.10,
):
    if ewma_throughput <= 0:
        return representations[0]

    safe_throughput = max(ewma_throughput - k_std * std_throughput, 0.0)

    jitter_penalty = min(jitter_ewma_ms / jitter_ref_ms, 1.0) * jitter_penalty_max
    safe_throughput *= (1 - jitter_penalty)

    if buffer_level_s >= buffer_boost_threshold:
        safe_throughput *= buffer_boost_factor

    selected = representations[0]
    for representation in representations:
        if representation["bitrate_kbps"] > safe_throughput:
            break
        selected = representation
    return selected

def simulate_policy(trace, policy_name, segment_duration_s, history_window=5):
    throughput_history = deque(maxlen=history_window)
    buffer_level_s = 0.0
    playback_started = False
    results = []

    for sample in trace:
        buffer_can_play = buffer_level_s >= 0.1

        if policy_name == "baseline_rate_based":
            representation = select_rate_based(REPRESENTATIONS, throughput_history)
        elif policy_name == "buffer_based":
            representation = select_buffer_based(REPRESENTATIONS, buffer_level_s)
        #elif policy_name == "hybrid":
            #representation = select_rate_based(REPRESENTATIONS, TODO)
        else:
            raise ValueError(f"Politica desconhecida: {policy_name}")

        throughput_kbps = sample["throughput_kbps"]
        bitrate_kbps = representation["bitrate_kbps"]
        download_time_s = (segment_duration_s * bitrate_kbps) / throughput_kbps

        rebuffer_event = 0
        stall_duration_s = 0.0
        if playback_started:
            if download_time_s > buffer_level_s:
                rebuffer_event = 1
                stall_duration_s = download_time_s - buffer_level_s
                buffer_level_s = 0.0
            else:
                buffer_level_s -= download_time_s

        buffer_level_s += segment_duration_s
        playback_started = buffer_level_s >= 0.1
        throughput_history.append(throughput_kbps)
        # todo entenda
        results.append(
            {
                "segment": sample["segment"],
                "timestamp": sample["timestamp"],
                "server_id": sample["server_id"],
                "quality": representation["quality"],
                "bitrate_kbps": bitrate_kbps,
                "vazao_kbps": round(throughput_kbps, 2),
                "download_time_s": round(download_time_s, 3),
                "variacao de atraso (jitter)_network_ms": round(sample["jitter_network_ms"], 2),
                "variacao de atraso (jitter)_ewma_ms": round(sample["jitter_ewma_ms"], 2),
                "buffer_level_s": round(buffer_level_s, 2),
                "buffer_can_play": 1 if buffer_can_play else 0,
                "rebuffer_event": rebuffer_event,
                "stall_duration_s": round(stall_duration_s, 3),
                "failover_total": sample["failover_total"],
            }
        )

    return results

def save_csv(path, rows): # todo mudar pra logger
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

def summarize(rows):
    bitrates = [float(row["bitrate_kbps"]) for row in rows]
    throughputs = [float(row["vazao_kbps"]) for row in rows]
    buffers = [float(row["buffer_level_s"]) for row in rows]
    qualities = [row["quality"] for row in rows]
    utilization = [bitrate / throughput for bitrate, throughput in zip(bitrates, throughputs)]
    switches = sum(1 for previous, current in zip(qualities, qualities[1:]) if previous != current)

    return {
        "avg_throughput_kbps": sum(throughputs) / len(throughputs),
        "avg_bitrate_kbps": sum(bitrates) / len(bitrates),
        "avg_utilization": sum(utilization) / len(utilization),
        "switches": switches,
        "rebuffer_events": sum(int(row["rebuffer_event"]) for row in rows),
        "stall_total_s": sum(float(row["stall_duration_s"]) for row in rows),
        "final_buffer_s": buffers[-1],
    }

def plot_comparison(baseline_rows, policy2_rows, plots_dir): # todo mudar pra plotter
    os.makedirs(plots_dir, exist_ok=True)

    segments = [int(row["segment"]) for row in baseline_rows]
    throughputs = [float(row["vazao_kbps"]) for row in baseline_rows]
    baseline_bitrates = [float(row["bitrate_kbps"]) for row in baseline_rows]
    policy2_bitrates = [float(row["bitrate_kbps"]) for row in policy2_rows]
    baseline_buffers = [float(row["buffer_level_s"]) for row in baseline_rows]
    policy2_buffers = [float(row["buffer_level_s"]) for row in policy2_rows]

    plt.figure(figsize=(10, 6))
    plt.plot(segments, throughputs, marker="o", linewidth=2, label="Vazao medida")
    plt.plot(segments, baseline_bitrates, marker="s", linewidth=2, label="Politica 1")
    plt.plot(segments, policy2_bitrates, marker="^", linewidth=2, label="Politica 2")
    plt.xlabel("Segmento")
    plt.ylabel("kbps")
    plt.title("Vazao e bitrate escolhido")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "politica2_throughput_bitrate_overlay.png"), dpi=300)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.step(segments, baseline_bitrates, where="mid", linewidth=2, label="Politica 1")
    plt.step(segments, policy2_bitrates, where="mid", linewidth=2, label="Politica 2")
    plt.xlabel("Segmento")
    plt.ylabel("Bitrate selecionado (kbps)")
    plt.title("Comparacao de qualidade selecionada")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "politica2_quality_comparison.png"), dpi=300)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(segments, baseline_buffers, marker="s", linewidth=2, label="Politica 1")
    plt.plot(segments, policy2_buffers, marker="^", linewidth=2, label="Politica 2")
    plt.xlabel("Segmento")
    plt.ylabel("Buffer (s)")
    plt.title("Comparacao do nivel de buffer")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "politica2_buffer_comparison.png"), dpi=300)
    plt.close()


def plot_three_way_comparison(baseline_rows, policy2_rows, policy3_rows, plots_dir, jitter_ref_ms=80.0):
    # Gráficos comparando as 3 políticas no mesmo trace de vazão (mesma escala,
    # mesmo cenário), exigidos no relatório final. Não sobrescreve os arquivos
    # politica2_*.png já referenciados no relatório da Entrega 2.
    os.makedirs(plots_dir, exist_ok=True)

    segments = [int(row["segment"]) for row in baseline_rows]
    throughputs = [float(row["vazao_kbps"]) for row in baseline_rows]
    bitrates_p1 = [float(row["bitrate_kbps"]) for row in baseline_rows]
    bitrates_p2 = [float(row["bitrate_kbps"]) for row in policy2_rows]
    bitrates_p3 = [float(row["bitrate_kbps"]) for row in policy3_rows]
    buffers_p1 = [float(row["buffer_level_s"]) for row in baseline_rows]
    buffers_p2 = [float(row["buffer_level_s"]) for row in policy2_rows]
    buffers_p3 = [float(row["buffer_level_s"]) for row in policy3_rows]
    jitter_ewma = [float(row["variacao de atraso (jitter)_ewma_ms"]) for row in baseline_rows]

    plt.figure(figsize=(10, 6))
    plt.plot(segments, throughputs, marker="o", linewidth=2, label="Vazao medida")
    plt.plot(segments, bitrates_p1, marker="s", linewidth=2, label="Politica 1 (Rate-Based)")
    plt.plot(segments, bitrates_p2, marker="^", linewidth=2, label="Politica 2 (Buffer-Based)")
    plt.plot(segments, bitrates_p3, marker="d", linewidth=2, label="Politica 3 (Hibrida EWMA+Jitter)")
    plt.xlabel("Segmento")
    plt.ylabel("kbps")
    plt.title("Vazao e bitrate escolhido - 3 politicas, mesmo trace")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "politica3_throughput_bitrate_overlay.png"), dpi=300)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.step(segments, bitrates_p1, where="mid", linewidth=2, label="Politica 1")
    plt.step(segments, bitrates_p2, where="mid", linewidth=2, label="Politica 2")
    plt.step(segments, bitrates_p3, where="mid", linewidth=2, label="Politica 3")
    plt.xlabel("Segmento")
    plt.ylabel("Bitrate selecionado (kbps)")
    plt.title("Comparacao de qualidade selecionada - 3 politicas")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "politica3_quality_comparison.png"), dpi=300)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(segments, buffers_p1, marker="s", linewidth=2, label="Politica 1")
    plt.plot(segments, buffers_p2, marker="^", linewidth=2, label="Politica 2")
    plt.plot(segments, buffers_p3, marker="d", linewidth=2, label="Politica 3")
    plt.xlabel("Segmento")
    plt.ylabel("Buffer (s)")
    plt.title("Comparacao do nivel de buffer - 3 politicas")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "politica3_buffer_comparison.png"), dpi=300)
    plt.close()

    plt.figure(figsize=(10, 6))
    plt.plot(segments, jitter_ewma, marker="o", linewidth=2, color="#6A4C93", label="Jitter EWMA (ms)")
    plt.axhline(y=jitter_ref_ms, color="red", linestyle="--", linewidth=1.5,
                label=f"Referencia usada na Politica 3 ({jitter_ref_ms:.0f} ms)")
    plt.xlabel("Segmento")
    plt.ylabel("Jitter EWMA (ms)")
    plt.title("Variacao de atraso (jitter) EWMA ao longo dos segmentos")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "politica3_jitter_ewma.png"), dpi=300)
    plt.close()


def save_summary(path, summaries):
    # summaries: lista de tuplas (rotulo, summary_dict), em qualquer quantidade.
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "policy",
        "avg_throughput_kbps",
        "avg_bitrate_kbps",
        "avg_utilization_percent",
        "switches",
        "rebuffer_events",
        "stall_total_s",
        "final_buffer_s",
    ]

    rows = []
    for policy, summary in summaries:
        rows.append(
            {
                "policy": policy,
                "avg_throughput_kbps": round(summary["avg_throughput_kbps"], 2),
                "avg_bitrate_kbps": round(summary["avg_bitrate_kbps"], 2),
                "avg_utilization_percent": round(summary["avg_utilization"] * 100, 2),
                "switches": summary["switches"],
                "rebuffer_events": summary["rebuffer_events"],
                "stall_total_s": round(summary["stall_total_s"], 3),
                "final_buffer_s": round(summary["final_buffer_s"], 2),
            }
        )

    with open(path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------
# Cenário sintético de jitter alto (demonstração isolada, não é dado oficial)
# ---------------------------------------------------------------------
#
# O trace real coletado pode não conter um episódio de jitter alto. Para
# tratar explicitamente esse cenário (exigido na Tarefa 3) mesmo que ele não
# apareça espontaneamente na coleta real, este gerador cria um trace
# SINTÉTICO com a MESMA vazão média ao longo de todo o trace, mas com o
# jitter EWMA subindo bastante na segunda metade. Isso isola o efeito do
# jitter (vazão constante, só o jitter muda) e mostra que a Politica 3 reage
# a essa mudança enquanto a Politica 1 e a Politica 2 não. Os resultados são
# salvos com o prefixo "synthetic_jitter_" para nao se misturarem com os
# dados reais da sessao oficial.

def generate_synthetic_jitter_trace(n_segments=30, base_throughput_kbps=900.0,
                                     jitter_low_ms=10.0, jitter_high_ms=200.0,
                                     switch_at=15, segment_duration_s=2.0, seed=42):
    import random
    rng = random.Random(seed)
    trace = []
    for i in range(1, n_segments + 1):
        throughput = base_throughput_kbps + rng.uniform(-20, 20)
        jitter_ewma = jitter_low_ms if i < switch_at else jitter_high_ms
        trace.append(
            {
                "segment": i,
                "timestamp": "",
                "server_id": "A",
                "throughput_kbps": throughput,
                "jitter_network_ms": jitter_ewma,
                "jitter_ewma_ms": jitter_ewma,
                "failover_total": 0,
            }
        )
    return trace, segment_duration_s


def run_synthetic_jitter_demo(csvs_dir, plots_dir):
    trace, segment_duration_s = generate_synthetic_jitter_trace()

    rows_p1 = simulate_policy(trace, "baseline_rate_based", segment_duration_s)
    rows_p2 = simulate_policy(trace, "buffer_based", segment_duration_s)
    rows_p3 = simulate_policy(trace, "policy3_hybrid", segment_duration_s)

    save_csv(os.path.join(csvs_dir, "synthetic_jitter_policy1.csv"), rows_p1)
    save_csv(os.path.join(csvs_dir, "synthetic_jitter_policy2.csv"), rows_p2)
    save_csv(os.path.join(csvs_dir, "synthetic_jitter_policy3.csv"), rows_p3)

    os.makedirs(plots_dir, exist_ok=True)
    segments = [row["segment"] for row in rows_p1]
    bitrates_p1 = [float(row["bitrate_kbps"]) for row in rows_p1]
    bitrates_p2 = [float(row["bitrate_kbps"]) for row in rows_p2]
    bitrates_p3 = [float(row["bitrate_kbps"]) for row in rows_p3]
    jitter_ewma = [float(row["variacao de atraso (jitter)_ewma_ms"]) for row in rows_p1]

    fig, axes = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
    axes[0].step(segments, bitrates_p1, where="mid", linewidth=2, label="Politica 1")
    axes[0].step(segments, bitrates_p2, where="mid", linewidth=2, label="Politica 2")
    axes[0].step(segments, bitrates_p3, where="mid", linewidth=2, label="Politica 3")
    axes[0].set_ylabel("Bitrate (kbps)")
    axes[0].set_title("Cenario sintetico: vazao constante, jitter sobe no segmento 15")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(segments, jitter_ewma, marker="o", color="#6A4C93")
    axes[1].axvline(x=15, color="red", linestyle=":", label="Jitter sobe aqui")
    axes[1].set_xlabel("Segmento")
    axes[1].set_ylabel("Jitter EWMA (ms)")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    out_path = os.path.join(plots_dir, "synthetic_jitter_demo.png")
    plt.savefig(out_path, dpi=300)
    plt.close()

    print("\n=== Demonstracao sintetica de jitter alto (NAO e dado oficial da sessao) ===")
    print(f"Grafico: {out_path}")
    print("Bitrate medio Politica 1:", round(sum(bitrates_p1) / len(bitrates_p1), 2), "kbps")
    print("Bitrate medio Politica 2:", round(sum(bitrates_p2) / len(bitrates_p2), 2), "kbps")
    print("Bitrate medio Politica 3:", round(sum(bitrates_p3) / len(bitrates_p3), 2), "kbps")
    print("Bitrate Politica 3 antes da subida do jitter (seg 1-14):",
          round(sum(bitrates_p3[:14]) / 14, 2), "kbps")
    print("Bitrate Politica 3 depois da subida do jitter (seg 15-30):",
          round(sum(bitrates_p3[14:]) / len(bitrates_p3[14:]), 2), "kbps")




def main():
    parser = argparse.ArgumentParser(description="Compare ABR policies using the same throughput trace.")
    parser.add_argument("--input", default="csvs/metrics_20260608_220922.csv")
    parser.add_argument("--csvs-dir", default="csvs")
    parser.add_argument("--plots-dir", default="relatorios/plots")
    parser.add_argument("--segment-duration", type=float)
    parser.add_argument("--synthetic-jitter-demo", action="store_true",
                         help="Tambem gera uma demonstracao sintetica isolando o efeito do jitter alto.")
    args = parser.parse_args()

    trace = load_trace(args.input)
    segment_duration_s = args.segment_duration or estimate_segment_duration(args.input)

    baseline_rows = simulate_policy(trace, "baseline_rate_based", segment_duration_s)
    policy2_rows = simulate_policy(trace, "buffer_based", segment_duration_s)
    policy3_rows = simulate_policy(trace, "policy3_hybrid", segment_duration_s)

    baseline_csv = os.path.join(args.csvs_dir, "policy1_baseline_same_trace.csv")
    policy2_csv = os.path.join(args.csvs_dir, "policy2_buffer_based_same_trace.csv")
    policy3_csv = os.path.join(args.csvs_dir, "policy3_hybrid_same_trace.csv")
    summary_csv = os.path.join(args.csvs_dir, "policy_comparison_summary.csv")

    save_csv(baseline_csv, baseline_rows)
    save_csv(policy2_csv, policy2_rows)
    save_csv(policy3_csv, policy3_rows)

    baseline_summary = summarize(baseline_rows)
    policy2_summary = summarize(policy2_rows)
    policy3_summary = summarize(policy3_rows)

    save_summary(summary_csv, [
        ("Politica 1 - Rate-Based", baseline_summary),
        ("Politica 2 - Buffer-Based", policy2_summary),
        ("Politica 3 - Hibrida EWMA+Jitter", policy3_summary),
    ])

    # Mantém os gráficos politica2_*.png exatamente como estavam (referenciados
    # no relatório da Entrega 2) e adiciona os gráficos de 3 vias exigidos para
    # o relatório final.
    plot_comparison(baseline_rows, policy2_rows, args.plots_dir)
    plot_three_way_comparison(baseline_rows, policy2_rows, policy3_rows, args.plots_dir)

    print(f"Trace: {args.input}")
    print(f"Duracao de segmento usada: {segment_duration_s:.2f}s")
    print(f"CSV Politica 1: {baseline_csv}")
    print(f"CSV Politica 2: {policy2_csv}")
    print(f"CSV Politica 3: {policy3_csv}")
    print(f"Resumo: {summary_csv}")
    print("Politica 1:", baseline_summary)
    print("Politica 2:", policy2_summary)
    print("Politica 3:", policy3_summary)

    if args.synthetic_jitter_demo:
        run_synthetic_jitter_demo(args.csvs_dir, args.plots_dir)

if __name__ == "__main__":
    main()
