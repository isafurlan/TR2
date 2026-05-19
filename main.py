import requests # requisição HTTP -> CONVERSAR C/ O SERVIDOR
import json
import time

manifestUrl = "http://137.131.178.229:8080/manifest"

throughput_history = []

def baixar_manifest():
    req = requests.get(manifestUrl) # Download
    req.raise_for_status() # Verifica erro
    manifest = req.json() # JSON -> Python
    return manifest

def parser_manifest(manifest):
    version = manifest["version"]
    segment_duration = manifest["segment_duration_s"]
    servers = sorted(
        manifest["servers"],
        key=lambda s: s["priority"]
    )
    representations = sorted(
        manifest["representations"],
        key=lambda r: r["bitrate_kbps"]
    )

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
    time_seconds = end - start
    throughput_kbps = (size_in_bytes * 8) / time_seconds / 1000
    return throughput_kbps

def main():
    manifest = baixar_manifest()
    parsed = parser_manifest(manifest)
    print(json.dumps(parsed))
    server_url = parsed["servers"][0]["url"]
    representations = parsed["representations"]
    for i in range(10):
        print(f"\nsegment {i + 1}:")
        quality = select_quality(representations, average)
        print(f"    selected quality:          {quality["quality"]}, {quality["bitrate_kbps"]}kbps")
        throughput = download_segment(server_url + quality["url_path"])
        print(f"    measured throughput:       {throughput:.2f}kbps")
        add_measurement(throughput)
        average = average_throughput()
        print(f"    current average bandwidth: {average:.2f}kbps")

if __name__ == '__main__':
    main()
