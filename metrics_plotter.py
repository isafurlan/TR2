import matplotlib.pyplot as plt
import glob
import os

class MetricsPlotter:
    def __init__(self, metrics_logger):
        self.metrics_logger = metrics_logger
        self.plots_dir = "relatorios/plots"

        # Cria pasta para salvar os gráficos se não existir
        if not os.path.exists(self.plots_dir):
            os.makedirs(self.plots_dir)

    def clear_old_plots(self):
        for plot_file in glob.glob(os.path.join(self.plots_dir, "*.png")):
            os.remove(plot_file)

    def mark_failovers(self, ax=None):
        failovers = [(int(m['segment']), 'green' if m['buffer_absorbed_failover'] == 1 else 'red')
                     for m in self.metrics_logger.metrics_data if m['failover_occurred']]
        added = set()
        for seg, color in failovers:
            legend = 'Failover (Absorvida pelo Buffer)' if color == 'green' else 'Failover (Causou Rebuffering)'
            current_legend = None if legend in added else legend
            added.add(legend)
            if ax is None:
                plt.axvline(seg, color=color, linestyle=':', linewidth=1.5, alpha=0.5, label=current_legend)
            else:
                ax.axvline(seg, color=color, linestyle=':', linewidth=1.5, alpha=0.5, label=current_legend)


    def plot_throughput_over_time(self, save=True, show=True):
        if not self.metrics_logger.metrics_data:
            print("Sem dados para plotar.")
            return

        segments = [m['segment'] for m in self.metrics_logger.metrics_data]
        throughputs = [m['vazao_kbps'] for m in self.metrics_logger.metrics_data]

        plt.figure(figsize=(10, 6))

        self.mark_failovers()

        plt.plot(segments, throughputs, marker='o', linestyle='-',
                 linewidth=2, markersize=6, color='#2E86AB')

        avg_throughput = sum(throughputs) / len(throughputs)
        plt.axhline(y=avg_throughput, color='#A23B72', linestyle='--',
                    linewidth=2, label=f'Média: {avg_throughput:.2f} kbps')

        plt.xlabel('Segmento', fontsize=12, fontweight='bold')
        plt.ylabel('Vazão (kbps)', fontsize=12, fontweight='bold')
        plt.title('Vazão ao Longo dos Segmentos', fontsize=14, fontweight='bold')
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save:
            filename = os.path.join(self.plots_dir, 'throughput_over_time.png')
            plt.savefig(filename, dpi=300)
            print(f"Gráfico de vazão salvo em: {filename}")

        if show:
            plt.show()

        plt.close()

    def plot_quality_over_time(self, save=True, show=True):
        if not self.metrics_logger.metrics_data:
            print("Sem dados para plotar.")
            return

        segments = [m['segment'] for m in self.metrics_logger.metrics_data]
        bitrates = [m['bitrate_kbps'] for m in self.metrics_logger.metrics_data]
        qualities = [m['quality'] for m in self.metrics_logger.metrics_data]

        plt.figure(figsize=(10, 6))
        plt.plot(segments, bitrates, marker='s', linestyle='-',
                 linewidth=2, markersize=6, color='#F18F01')

        plt.xlabel('Segmento', fontsize=12, fontweight='bold')
        plt.ylabel('Bitrate (kbps)', fontsize=12, fontweight='bold')
        plt.title('Qualidade (Bitrate) ao Longo dos Segmentos',
                  fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3)

        for i, (seg, br, qual) in enumerate(zip(segments, bitrates, qualities)):
            plt.annotate(qual, (seg, br), textcoords="offset points",
                        xytext=(0,10), ha='center', fontsize=8)

        plt.tight_layout()

        if save:
            filename = os.path.join(self.plots_dir, 'quality_over_time.png')
            plt.savefig(filename, dpi=300)
            print(f"Gráfico de qualidade salvo em: {filename}")

        if show:
            plt.show()

        plt.close()

    def plot_buffer_level_over_time(self, save=True, show=True):
        if not self.metrics_logger.metrics_data:
            print("Sem dados para plotar.")
            return

        segments = [m['segment'] for m in self.metrics_logger.metrics_data]
        buffer_levels = [m['buffer_level_s'] for m in self.metrics_logger.metrics_data]

        plt.figure(figsize=(10, 6))

        self.mark_failovers()

        plt.plot(segments, buffer_levels, marker='^', linestyle='-',
                 linewidth=2, markersize=6, color='#C73E1D')

        min_buffer = 2.0
        plt.axhline(y=min_buffer, color='red', linestyle=':',
                    linewidth=2, label=f'Buffer mínimo ({min_buffer}s)')

        plt.xlabel('Segmento', fontsize=12, fontweight='bold')
        plt.ylabel('Nível do Buffer (segundos)', fontsize=12, fontweight='bold')
        plt.title('Nível do Buffer ao Longo do Tempo', fontsize=14, fontweight='bold')
        plt.legend(loc='best')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save:
            filename = os.path.join(self.plots_dir, 'buffer_level_over_time.png')
            plt.savefig(filename, dpi=300)
            print(f"Gráfico de buffer salvo em: {filename}")

        if show:
            plt.show()

        plt.close()

    def plot_jitter_over_time(self, save=True, show=True):
        if not self.metrics_logger.metrics_data:
            return

        segments = [m['segment'] for m in self.metrics_logger.metrics_data]
        jitter_network = [m['variacao de atraso (jitter)_network_ms'] for m in self.metrics_logger.metrics_data]
        jitter_ewma = [m['variacao de atraso (jitter)_ewma_ms'] for m in self.metrics_logger.metrics_data]

        plt.figure(figsize=(10, 6))
        plt.plot(segments, jitter_network, marker='o', label='Jitter Network')
        plt.plot(segments, jitter_ewma, marker='s', label='Jitter EWMA')
        plt.xlabel('Segmento')
        plt.ylabel('Jitter (ms)')
        plt.title('Jitter ao Longo dos Segmentos')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save:
            filename = os.path.join(self.plots_dir, 'jitter_over_time.png')
            plt.savefig(filename, dpi=300)

        if show:
            plt.show()

        plt.close()

    def plot_stall_metrics(self, save=True, show=True):
        if not self.metrics_logger.metrics_data:
            return

        segments = [m['segment'] for m in self.metrics_logger.metrics_data]
        stalls = [m['stall_duration_s'] for m in self.metrics_logger.metrics_data]
        cumulative = []
        total = 0.0

        for stall in stalls:
            total += stall
            cumulative.append(total)

        plt.figure(figsize=(10, 6))
        self.mark_failovers()
        plt.bar(segments, stalls, label='Stall por Segmento')
        plt.plot(segments, cumulative, marker='o', linewidth=2, label='Stall Acumulado')
        plt.xlabel('Segmento')
        plt.ylabel('Tempo (s)')
        plt.title('Rebuffering / Stall')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        if save:
            filename = os.path.join(self.plots_dir, 'stall_metrics.png')
            plt.savefig(filename, dpi=300)

        if show:
            plt.show()

        plt.close()

    def plot_combined_metrics(self, save=True, show=True):
        if not self.metrics_logger.metrics_data:
            print("Sem dados para plotar.")
            return

        segments = [m['segment'] for m in self.metrics_logger.metrics_data]
        # CORREÇÃO: Usando 'vazao_kbps'
        throughputs = [m['vazao_kbps'] for m in self.metrics_logger.metrics_data]
        bitrates = [m['bitrate_kbps'] for m in self.metrics_logger.metrics_data]

        fig, axes = plt.subplots(2, 1, figsize=(12, 10))

        # Subplot 1: Vazão
        self.mark_failovers(axes[0])
        axes[0].plot(segments, throughputs, marker='o', linestyle='-',
                     linewidth=2, markersize=6, color='#2E86AB', label='Vazão Medida')
        axes[0].axhline(y=sum(throughputs)/len(throughputs), color='#A23B72',
                       linestyle='--', linewidth=2, alpha=0.7, label='Média')
        axes[0].set_ylabel('Vazão (kbps)', fontsize=11, fontweight='bold')
        axes[0].set_title('Métricas de Desempenho', fontsize=13, fontweight='bold')
        axes[0].legend(loc='best')
        axes[0].grid(True, alpha=0.3)

        # Subplot 2: Bitrate/Qualidade
        axes[1].plot(segments, bitrates, marker='s', linestyle='-',
                     linewidth=2, markersize=6, color='#F18F01', label='Qualidade Selecionada')
        axes[1].set_xlabel('Segmento', fontsize=11, fontweight='bold')
        axes[1].set_ylabel('Bitrate (kbps)', fontsize=11, fontweight='bold')
        axes[1].legend(loc='best')
        axes[1].grid(True, alpha=0.3)

        plt.tight_layout()

        if save:
            filename = os.path.join(self.plots_dir, 'combined_metrics.png')
            plt.savefig(filename, dpi=300)
            print(f"Gráfico combinado salvo em: {filename}")

        if show:
            plt.show()

        plt.close()

    def generate_all_plots(self):
        print("\n=== Gerando Gráficos ===")
        self.clear_old_plots()
        self.plot_throughput_over_time(save=True, show=False)
        self.plot_quality_over_time(save=True, show=False)
        self.plot_buffer_level_over_time(save=True, show=False)
        self.plot_jitter_over_time(save=True, show=False)
        self.plot_stall_metrics(save=True, show=False)
        self.plot_combined_metrics(save=True, show=False)
        print("Todos os gráficos foram gerados!\n")
