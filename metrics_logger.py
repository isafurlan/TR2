import csv
import os
import glob
from datetime import datetime

class MetricsLogger:
    def __init__(self, filename=None):
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"metrics_{timestamp}.csv"
        self.filename = filename
        self.csvs_dir = "csvs"
        self.metrics_data = []

        if not os.path.exists(self.csvs_dir):
            os.makedirs(self.csvs_dir)

    def clear_old_csvs(self, policy):
        for filename in glob.glob(os.path.join(self.csvs_dir, f"*_policy{policy}_*.csv")):
            os.remove(filename)

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
            'vazão_kbps', 'download_time_s',
            'variação de atraso (jitter)_network_ms', 'variação de atraso (jitter)_ewma_ms',
            'buffer_level_s', 'buffer_can_play', 'rebuffer_event',
            'stall_duration_s', 'failover_total'
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for m in self.metrics_data:
                # Criamos um dicionário limpo apenas com o que o 'fieldnames' aceita
                row_filtrada = {
                    'segment': m['segment'],
                    'timestamp': m['timestamp'],
                    'server_id': m['server_id'],
                    'quality': m['quality'],
                    'bitrate_kbps': m['bitrate_kbps'],
                    'vazão_kbps': m['vazao_kbps'],
                    'download_time_s': m['download_time_s'],
                    'variação de atraso (jitter)_network_ms': m['variacao de atraso (jitter)_network_ms'],
                    'variação de atraso (jitter)_ewma_ms': m['variacao de atraso (jitter)_ewma_ms'],
                    'buffer_level_s': m['buffer_level_s'],
                    'buffer_can_play': m['buffer_can_play'],
                    'rebuffer_event': m['rebuffer_event'],
                    'stall_duration_s': m['stall_duration_s'],
                    'failover_total': m['failover_total']
                }
                writer.writerow(row_filtrada)

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

    def save_global_summary(self, policy_id, policy_name):
        """Salva uma linha resumida e garante que não haja duplicatas da mesma política."""
        stats = self.get_summary_stats()
        if not stats: return

        os.makedirs(self.csvs_dir, exist_ok=True)
        filepath = os.path.join(self.csvs_dir, "comparacao.csv")

        # 1. Lê todas as linhas existentes (se o arquivo existir)
        linhas = []
        if os.path.isfile(filepath):
            with open(filepath, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                # Filtra: mantém apenas as políticas que NÃO são a atual
                linhas = [row for row in reader if row['Politica'] != str(policy_id)]

        # 2. Adiciona a nova linha com os dados atualizados
        linhas.append({
            'Politica': policy_id,
            'Nome': policy_name,
            'Vazao Media (kbps)': f"{stats['avg_throughput_kbps']:.2f}",
            'Rebufferings': stats['rebuffering_events'],
            'Stall Total (s)': f"{stats['total_stall_time_s']:.2f}",
            'Failovers': stats['total_failovers'],
            'Tempo Medio Failover': f"{stats['avg_failover_time']:.2f}"
        })

        # 3. Reescreve o arquivo com a lista limpa e atualizada
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Politica', 'Nome', 'Vazao Media (kbps)', 'Rebufferings', 'Stall Total (s)', 'Failovers',
                          'Tempo Medio Failover']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(linhas)
