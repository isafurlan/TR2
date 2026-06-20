import csv
import os
from datetime import datetime

class MetricsLogger:
    def __init__(self, filename=None):
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{timestamp}.csv"
        self.filename = filename
        self.csvs_dir = "csvs"
        self.metrics_data = []

    def log_segment(self, segment_index, throughput_kbps, download_time_s,
                    jitter_network_ms, jitter_ewma_ms, buffer_level,
                    quality, bitrate, buffer_can_play, rebuffered,
                    stall_duration, server_id, failover_total, failover_occurred,
                    failover_time, buffer_absorbed_failover, server_before, server_after):

        metric = {
            'segment': segment_index,
            'timestamp': datetime.now().isoformat(),
            'server_id': server_id,
            'quality': quality,
            'bitrate_kbps': bitrate,
            'vazao_kbps': round(throughput_kbps, 2),
            'download_time_s': round(download_time_s, 3),
            'variacao de atraso (jitter)_network_ms': round(jitter_network_ms, 2),
            'variacao de atraso (jitter)_ewma_ms': round(jitter_ewma_ms, 2),
            'buffer_level_s': round(buffer_level, 2),
            'buffer_can_play': 1 if buffer_can_play else 0,
            'rebuffer_event': 1 if rebuffered else 0,
            'stall_duration_s': round(stall_duration, 3),
            'failover_total': failover_total,
            'failover_occurred': 1 if failover_occurred else 0,
            'failover_time': failover_time,
            'buffer_absorbed_failover': '' if buffer_absorbed_failover is None else int(buffer_absorbed_failover),
            'server_before': server_before,
            'server_after': server_after
        }
        self.metrics_data.append(metric)

    def save_to_csv(self):
        if not self.metrics_data:
            print("Nenhuma métrica para salvar.")
            return

        os.makedirs(self.csvs_dir, exist_ok=True)
        filepath = os.path.join(self.csvs_dir, self.filename)

        fieldnames = [
            'segment', 'timestamp', 'server_id', 'quality', 'bitrate_kbps',
            'vazao_kbps', 'download_time_s',
            'variacao de atraso (jitter)_network_ms', 'variacao de atraso (jitter)_ewma_ms',
            'buffer_level_s', 'buffer_can_play', 'rebuffer_event',
            'stall_duration_s', 'failover_total', 'failover_occurred', 'failover_time',
            'buffer_absorbed_failover', 'server_before', 'server_after'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.metrics_data)

        print(f"Métricas salvas em: {filepath}")

    def get_summary_stats(self):
        if not self.metrics_data:
            return None

        vazoes = [m['vazao_kbps'] for m in self.metrics_data]
        buffer_levels = [m['buffer_level_s'] for m in self.metrics_data]
        rebufferings = sum(m['rebuffer_event'] for m in self.metrics_data)
        stalls = sum(m['stall_duration_s'] for m in self.metrics_data)
        failovers = sum(m['failover_occurred'] for m in self.metrics_data)
        avg_failover_time = sum(m['failover_time'] for m in self.metrics_data if m['failover_occurred']) / failovers if failovers > 0 else 0

        return {
            'total_segments': len(self.metrics_data),
            'avg_throughput_kbps': sum(vazoes) / len(vazoes),
            'min_throughput_kbps': min(vazoes),
            'max_throughput_kbps': max(vazoes),
            'avg_buffer_level_s': sum(buffer_levels) / len(buffer_levels),
            'rebuffering_events': rebufferings,
            'total_stall_time_s': stalls,
            'total_failovers': failovers,
            'avg_failover_time': avg_failover_time
        }
