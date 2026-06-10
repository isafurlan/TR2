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

    def plot_throughput_over_time(self, save=True, show=True):
        if not self.metrics_logger.metrics_data:
            print("Sem dados para plotar.")
            return

        segments = [m['segment'] for m in self.metrics_logger.metrics_data]
        throughputs = [m['vazao_kbps'] for m in self.metrics_logger.metrics_data]
        failovers = [m['segment'] for m in self.metrics_logger.metrics_data if m['failover_occurred']]

        plt.figure(figsize=(10, 6))

        for seg in failovers:
            plt.axvline(seg, linestyle=':', alpha=0.5)

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
        failovers = [m['segment'] for m in self.metrics_logger.metrics_data if m['failover_occurred']]

        fig, axes = plt.subplots(2, 1, figsize=(12, 10))

        # Subplot 1: Vazão
        for seg in failovers:
            axes[0].axvline(seg, linestyle=':', alpha=0.5)
        axes[0].plot(segments, throughputs, marker='o', linestyle='-',
                     linewidth=2, markersize=6, color='#2E86AB')
        axes[0].axhline(y=sum(throughputs)/len(throughputs), color='#A23B72',
                       linestyle='--', linewidth=2, alpha=0.7)
        axes[0].set_ylabel('Vazão (kbps)', fontsize=11, fontweight='bold')
        axes[0].set_title('Métricas de Desempenho', fontsize=13, fontweight='bold')
        axes[0].legend(['Vazão Medida', 'Média'], loc='best')
        axes[0].grid(True, alpha=0.3)

        # Subplot 2: Bitrate/Qualidade
        for seg in failovers:
            axes[1].axvline(seg, linestyle=':', alpha=0.5)
        axes[1].plot(segments, bitrates, marker='s', linestyle='-',
                     linewidth=2, markersize=6, color='#F18F01')
        axes[1].set_xlabel('Segmento', fontsize=11, fontweight='bold')
        axes[1].set_ylabel('Bitrate (kbps)', fontsize=11, fontweight='bold')
        axes[1].legend(['Qualidade Selecionada'], loc='best')
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
        self.plot_stall_metrics(save=True, show=False)
        self.plot_combined_metrics(save=True, show=False)
        print("Todos os gráficos foram gerados!\n")
