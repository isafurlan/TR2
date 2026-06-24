import urllib.request
import urllib.error

import json
import time

import argparse

from datetime import datetime
from urllib.parse import urljoin

from buffer_manager import BufferManager
from metrics_logger import MetricsLogger
from metrics_plotter import MetricsPlotter
from server_manager import ServerManager

manifestUrl = "http://137.131.178.229:8080/manifest"
throughput_history = []
throughput_ewma = None

POLICY_NAMES = {
    "1": "Rate-Based (baseline)",
    "2": "Buffer-Based",
    "3": "Hibrida EWMA + desvio padrao + penalidade de jitter",
}


def baixar_manifest(url):
    try:
        with urllib.request.urlopen(url) as resposta:
            dados_bytes = resposta.read()
            texto = dados_bytes.decode('utf-8')
            manifest_dict = json.loads(texto)
            return manifest_dict

    except urllib.error.URLError as erro:
        print(f"Falha na requisição: {erro}")
        try:
            with open("manifest_local.json", "r") as arq:
                return json.load(arq)
        except FileNotFoundError:
            return None

        return None


def parser_manifest(manifest):
    version = manifest["version"]
    segment_duration = manifest["segment_duration_s"]
    servers = sorted(manifest["servers"], key=lambda s: s["priority"])
    representations = sorted(manifest["representations"], key=lambda r: r["bitrate_kbps"])
    return {
        "version": version,
        "segment_duration": segment_duration,
        "servers": servers,
        "representations": representations
    }


def add_measurement(throughput_kbps, window_size=5):
    global throughput_ewma
    throughput_history.append(throughput_kbps)
    if len(throughput_history) > window_size:
        throughput_history.pop(0)
    throughput_ewma = update_ewma(throughput_ewma, throughput_kbps)


def average_throughput():
    if not throughput_history:
        return 0
    return sum(throughput_history) / len(throughput_history)


def select_quality_RateBased(representations, avg, safety_factor=0.9):  # Todo: verificar sf, ta 85 em outros locais
    safe = avg * safety_factor
    selected = representations[0]
    for rep in representations:
        if rep["bitrate_kbps"] > safe:
            break
        selected = rep
    return selected


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


def select_quality_BufferBased(representations, buffer_level_s):
    indice = int(buffer_level_s // 3)
    if indice < len(representations):
        return representations[indice]
    return representations[-1]


def select_quality_Hybrid(representations, ewma_throughput, std_throughput, jitter_ewma_ms, buffer_level_s, k_std=1.0,
                          jitter_ref_ms=80.0, jitter_penalty_max=0.4, buffer_boost_threshold=10.0,
                          buffer_boost_factor=1.10, ):
    if ewma_throughput <= 0:
        return representations[0]

    safe_throughput = max(ewma_throughput - k_std * std_throughput, 0.0)

    jitter_penalty = min(jitter_ewma_ms / jitter_ref_ms, 1.0) * jitter_penalty_max
    safe_throughput *= (1 - jitter_penalty)

    if buffer_level_s >= buffer_boost_threshold:
        safe_throughput *= buffer_boost_factor

    selected = representations[0]
    for rep in representations:
        if rep["bitrate_kbps"] > safe_throughput:
            break
        selected = rep
    return selected


def download_segment(url):
    start = time.perf_counter()

    with urllib.request.urlopen(url, timeout=5) as response:
        size = len(response.read())
        end = time.perf_counter()
        duration = max(end - start, 0.001)
        throughput = (size * 8) / duration / 1000
        return throughput, duration


def build_segment_url(server_url, representation, segment_index):
    if representation.get("segments"):
        segments = representation["segments"]
        if segment_index > len(segments):
            raise IndexError(f"Segmento {segment_index} não existe no manifest.")
        path = segments[segment_index - 1]
    else:
        path = representation["url_path"]
        format_values = {
            "segment": segment_index,
            "segment_index": segment_index,
            "segment_number": segment_index,
            "index": segment_index,
            "number": segment_index,
            "quality": representation.get("quality"),
            "bitrate": representation.get("bitrate_kbps"),
            "bitrate_kbps": representation.get("bitrate_kbps"),
        }
        if "{" in path and "}" in path:
            path = path.format(segment_index, **format_values)

    return urljoin(server_url.rstrip("/") + "/", path.lstrip("/"))

def select_policy(policy, representations, avg_throughput, throughput_ewma_value, std_throughput, jitter_ewma_ms,
                  buffer_level_s):
    if policy == "1":
        return select_quality_RateBased(representations, avg_throughput)
    elif policy == "2":
        return select_quality_BufferBased(representations, buffer_level_s)
    elif policy == "3":
        return select_quality_Hybrid(
            representations,
            throughput_ewma_value if throughput_ewma_value is not None else 0.0,
            std_throughput,
            jitter_ewma_ms,
            buffer_level_s,
        )
    raise ValueError(f"Politica desconhecida: {policy}")


def main():
    throughput_history.clear()

    manifest = baixar_manifest(manifestUrl)
    if manifest is None:
        print("Erro ao baixar o manifest")
        return
    parsed = parser_manifest(manifest)

    # Escolha da Política
    parser = argparse.ArgumentParser(description="Cliente DASH adaptativo - TR2")
    parser.add_argument("--policy", choices=["1", "2", "3"], default="3",
                        help="Politica ABR: 1=Rate-Based (baseline, default), 2=Buffer-Based, 3=Hibrida EWMA+Jitter")
    args = parser.parse_args()

    throughput_history.clear()
    global throughput_ewma
    throughput_ewma = None

    representations = parsed["representations"]
    segment_duration = parsed['segment_duration']

    # Manda a duração do segmento pra calcular o buffer
    buffer_manager = BufferManager(segment_duration)

    # TODO: Organização do CSV
    timestamp = datetime.now().strftime("%d%m%Y_%H%M%S")
    metrics_logger = MetricsLogger(filename=f"metrics_policy{args.policy}_{timestamp}.csv")

    metrics_logger.clear_old_csvs(args.policy)

    # Manda os servidores do manifest
    server_manager = ServerManager(parsed["servers"])
    current_server = server_manager.current_server()
    server_url = current_server["url"]
    server_id = current_server["id"]

    print(json.dumps(parsed, indent=2))
    print(f"Politica ABR ativa: {args.policy} ({POLICY_NAMES[args.policy]})")
    print(f"Iniciando download de 10 segmentos...\n")

    # last_segment_time = time.perf_counter()
    jitter_ewma = 0.0
    alpha_ewma = 0.2
    failover_total = 0

    for i in range(30):
        failover_occurred = False
        failover_time = 0.0
        buffer_absorbed_failover = None
        server_before = server_id
        server_after = server_id

        print(f"--- Segmento {i + 1} ---")

        buffer_manager.regulate_buffer()
        can_play = buffer_manager.can_play()
        buffer_before_download = buffer_manager.get_buffer_level()
        quality = select_policy(args.policy, representations, average_throughput(), throughput_ewma,
                                rolling_std(throughput_history), jitter_ewma, buffer_before_download)


        print(f"Qualidade: {quality['quality']} ({quality['bitrate_kbps']}kbps)")
        print(f"Buffer: {buffer_before_download:.2f}s | Play: {can_play}")

        url_segmento = build_segment_url(server_url, quality, i + 1)
        failover_start = None

        try:
            # Força failover -> Injeção de falha
            '''if (i + 1) in (2, 10, 12, 21):
                raise urllib.error.URLError(f"{i + 1}")'''
            result = download_segment(url_segmento)
            if result is not None:
                throughput, download_time = result

        except (urllib.error.URLError, TimeoutError) as e:
            failover_occurred = True
            failover_start = time.perf_counter()
            new_server = server_manager.failover()

            erro_msg = str(e.reason) if hasattr(e, 'reason') else str(e)

            # força stall durante failover
            '''if erro_msg == "10":
                time.sleep(16)
            elif erro_msg == "12":
                time.sleep(5)'''

            if new_server is None:
                raise Exception("Nenhum servidor disponível")

            failover_total += 1
            server_before = server_id
            server_url = new_server["url"]
            server_id = new_server["id"]
            server_after = server_id

            print(f"FAILOVER -> servidor {server_id}")

            url_segmento = build_segment_url(server_url, quality, i + 1)
            result = download_segment(url_segmento)
            if result is not None:
                throughput, download_time = result

            failover_time = time.perf_counter() - failover_start

        stall_duration = buffer_manager.update_decay()
        rebuffered = stall_duration > 0
        buffer_manager.add_segment()

        # Cálculo Jitter Network
        if i == 0:
            jitter_network = 0.0
        else:
            jitter_network = abs(download_time - previous_download_time) * 1000
        previous_download_time = download_time

        # Cálculo Jitter EWMA
        if i == 0:
            jitter_ewma = jitter_network
        else:
            jitter_ewma = (alpha_ewma * jitter_network) + ((1 - alpha_ewma) * jitter_ewma)

        if rebuffered:
            print(f"REBUFFERING detectado: {stall_duration:.2f}s")
        if failover_occurred:
            buffer_absorbed_failover = not rebuffered

        # Registro no Logger
        metrics_logger.log_segment(
            segment_index=i + 1,
            throughput_kbps=throughput,
            download_time_s=download_time,
            jitter_network_ms=jitter_network,
            jitter_ewma_ms=jitter_ewma,
            buffer_level=buffer_manager.get_buffer_level(),
            quality=quality['quality'],
            bitrate=quality['bitrate_kbps'],
            buffer_can_play=can_play,
            rebuffered=rebuffered,
            stall_duration=stall_duration,
            server_id=server_id,
            failover_total=failover_total,
            failover_occurred=failover_occurred,
            failover_time=failover_time,
            buffer_absorbed_failover=buffer_absorbed_failover,
            server_before=server_before,
            server_after=server_after
        )

        add_measurement(throughput)
        print(f"Vazão: {throughput:.2f}kbps | Tempo: {download_time:.2f}s")
        print(f"Jitter Net: {jitter_network:.2f}ms | EWMA: {jitter_ewma:.2f}ms")
        print(f"Média: {average_throughput():.2f}kbps\n")

    print("=== Finalizando ===")
    metrics_logger.save_to_csv()

    plotter = MetricsPlotter(metrics_logger, args.policy)
    plotter.generate_all_plots()

    stats = metrics_logger.get_summary_stats()
    print("\n Resumo Final:")
    print(f"Segmentos: {stats['total_segments']}")
    print(f"Vazão média: {stats['avg_throughput_kbps']:.2f} kbps")
    print(f"Rebufferings: {stats['rebuffering_events']}")
    print(f"Stall total: {stats['total_stall_time_s']:.2f}s")
    print(f"Failovers': {stats['total_failovers']}"),
    print(f"Tempo médio de failover: {stats['avg_failover_time']:.2f}")

    nome_da_politica = POLICY_NAMES[args.policy]
    metrics_logger.save_global_summary(args.policy, nome_da_politica)


if __name__ == '__main__':
    main()
