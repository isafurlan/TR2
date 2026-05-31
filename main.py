import requests
import json
import time

from buffer_manager import BufferManager
from metrics_logger import MetricsLogger
from metrics_plotter import MetricsPlotter

manifestUrl = "http://137.131.178.229:8080/manifest"
throughput_history = []

def baixar_manifest():
    req = requests.get(manifestUrl)
    req.raise_for_status()
    return req.json()

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
    throughput_history.append(throughput_kbps)
    if len(throughput_history) > window_size:
        throughput_history.pop(0)

def average_throughput():
    if not throughput_history:
        return 0
    return sum(throughput_history) / len(throughput_history)

def select_quality(representations, avg, safety_factor=0.85):
    safe = avg * safety_factor
    selected = representations[0]
    for rep in representations:
        if rep["bitrate_kbps"] > safe:
            break
        selected = rep
    return selected

def download_segment(url):
    start = time.time()
    response = requests.get(url)
    response.raise_for_status()
    end = time.time()
    size_in_bytes = len(response.content)
    time_seconds = end - start if (end - start) > 0 else 0.001
    throughput_kbps = (size_in_bytes * 8) / time_seconds / 1000
    return throughput_kbps, time_seconds

def main():
    manifest = baixar_manifest()
    parsed = parser_manifest(manifest)
    
    buffer_manager = BufferManager(parsed['segment_duration'])
    metrics_logger = MetricsLogger()
    
    server_url = parsed["servers"][0]["url"]
    server_id = parsed["servers"][0].get("id", "A")
    representations = parsed["representations"]
    segment_duration = parsed['segment_duration']
    
    print(json.dumps(parsed, indent=2))
    print(f"Iniciando download de 10 segmentos...\n")

    last_segment_time = time.time()
    jitter_ewma = 0.0
    alpha_ewma = 0.2
    failover_total = 0
    last_server_id = server_id

    for i in range(10):
        print(f"--- Segmento {i + 1} ---")
        
        buffer_manager.update_decay()
        quality = select_quality(representations, average_throughput())
        can_play = buffer_manager.check_can_play()
        
        print(f"Qualidade: {quality['quality']} ({quality['bitrate_kbps']}kbps)")
        print(f"Buffer: {buffer_manager.get_buffer_level():.2f}s | Play: {can_play}")
        
        url_segmento = server_url + quality["url_path"]
        throughput, download_time = download_segment(url_segmento)
        buffer_manager.add_segment()
        
        # Cálculo Jitter Network
        current_time = time.time()
        if i == 0:
            jitter_network = 0.0
        else:
            inter_arrival = current_time - last_segment_time
            jitter_network = abs(inter_arrival - segment_duration) * 1000
        last_segment_time = current_time
        
        # Cálculo Jitter EWMA
        if i == 0:
            jitter_ewma = jitter_network
        else:
            jitter_ewma = (alpha_ewma * jitter_network) + ((1 - alpha_ewma) * jitter_ewma)
            
        # Verifica Rebuffering / Stall
        is_rebuffering = buffer_manager.is_rebuffering
        stall_duration = 0.0
        if is_rebuffering:
            print("⚠️ REBUFFERING! Esperando...")
            time.sleep(1.0)
            stall_duration = 1.0
            buffer_manager.record_rebuffering_end()
            
        # Rastreamento de Failover
        if server_id != last_server_id:
            failover_total += 1
            last_server_id = server_id
            
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
            is_rebuffering=is_rebuffering,
            stall_duration=stall_duration,
            server_id=server_id,
            failover_total=failover_total
        )
        
        add_measurement(throughput)
        print(f"Vazão: {throughput:.2f}kbps | Tempo: {download_time:.2f}s")
        print(f"Jitter Net: {jitter_network:.2f}ms | EWMA: {jitter_ewma:.2f}ms")
        print(f"Média: {average_throughput():.2f}kbps\n")

    print("=== Finalizando ===")
    metrics_logger.save_to_csv()
    
    plotter = MetricsPlotter(metrics_logger)
    plotter.generate_all_plots()
    
    stats = metrics_logger.get_summary_stats()
    print("\n📊 Resumo Final:")
    print(f"Segmentos: {stats['total_segments']}")
    print(f"Vazão média: {stats['avg_throughput_kbps']:.2f} kbps")
    print(f"Rebufferings: {stats['rebuffering_events']}")
    print(f"Stall total: {stats['total_stall_time_s']:.2f}s")

if __name__ == '__main__':
    main()