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
    if buffer_level_s < 4.0:
        return representations[0] # Menor qualidade
    elif buffer_level_s < 8.0:
        return representations[min(1, len(representations) - 1)]
    return representations[-1] # Maior qualidae

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

def save_csv(path, rows):
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

def plot_comparison(baseline_rows, policy2_rows, plots_dir):
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


def save_summary(path, baseline_summary, policy2_summary):
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
    for policy, summary in (
        ("Politica 1 - Rate-Based", baseline_summary),
        ("Politica 2 - Buffer-Based", policy2_summary),
    ):
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


def main():
    parser = argparse.ArgumentParser(description="Compare ABR policies using the same throughput trace.")
    parser.add_argument("--input", default="csvs/metrics_20260608_220922.csv")
    parser.add_argument("--csvs-dir", default="csvs")
    parser.add_argument("--plots-dir", default="relatorios/plots")
    parser.add_argument("--segment-duration", type=float)
    args = parser.parse_args()

    trace = load_trace(args.input)
    segment_duration_s = args.segment_duration or estimate_segment_duration(args.input)

    baseline_rows = simulate_policy(trace, "baseline_rate_based", segment_duration_s)
    policy2_rows = simulate_policy(trace, "buffer_based", segment_duration_s)

    baseline_csv = os.path.join(args.csvs_dir, "policy1_baseline_same_trace.csv")
    policy2_csv = os.path.join(args.csvs_dir, "policy2_buffer_based_same_trace.csv")
    summary_csv = os.path.join(args.csvs_dir, "policy_comparison_summary.csv")

    save_csv(baseline_csv, baseline_rows)
    save_csv(policy2_csv, policy2_rows)

    baseline_summary = summarize(baseline_rows)
    policy2_summary = summarize(policy2_rows)
    save_summary(summary_csv, baseline_summary, policy2_summary)
    plot_comparison(baseline_rows, policy2_rows, args.plots_dir)

    print(f"Trace: {args.input}")
    print(f"Duracao de segmento usada: {segment_duration_s:.2f}s")
    print(f"CSV Politica 1: {baseline_csv}")
    print(f"CSV Politica 2: {policy2_csv}")
    print(f"Resumo: {summary_csv}")
    print("Politica 1:", baseline_summary)
    print("Politica 2:", policy2_summary)

if __name__ == "__main__":
    main()
