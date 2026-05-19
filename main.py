import requests # requisição HTTP -> CONVERSAR C/ O SERVIDOR
import json

manifestUrl = "http://137.131.178.229:8080/manifest"

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

def main():
    manifest = baixar_manifest()
    parsed = parser_manifest(manifest)
    print(json.dumps(parsed))

if __name__ == '__main__':
    main()
