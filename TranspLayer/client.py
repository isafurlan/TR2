#!/usr/bin/env python3
"""
Cliente TCP — Trabalho Prático: Camada de Transporte
Disciplina de Teleinformática e Redes 2

Conecta ao servidor da disciplina e recebe um stream de dados por 60 segundos.
O servidor introduz eventos de pausa que provocam fenômenos TCP observáveis
no Wireshark: slow start, retransmissões, controle de congestionamento.

IMPORTANTE: inicie a captura no Wireshark ANTES de executar este programa.
    Filtro de captura : tcp port 9000
    Filtro de exibição: tcp.stream eq 0

Uso:
    python3 client.py --grupo GRUPOXX --host <IP_DO_SERVIDOR>
    python3 client.py --grupo GRUPO01
"""

import socket
import time
import json
import argparse
import sys


SERVER_HOST = "137.131.178.229"
SERVER_PORT = 9000
BUFFER_SIZE = 65536


def fmt_bytes(n):
    if n < 1024 ** 2:
        return f"{n/1024:.1f} KB"
    return f"{n/1024/1024:.2f} MB"

def fmt_tp(bps):
    if bps < 1024 ** 2:
        return f"{bps/1024:.1f} KB/s"
    return f"{bps/1024/1024:.2f} MB/s"


def run(grupo, host, port):
    print("=" * 60)
    print("  Trabalho Prático — Camada de Transporte")
    print("  Redes de Computadores")
    print("=" * 60)
    print(f"  Grupo   : {grupo}")
    print(f"  Servidor: {host}:{port}")
    print(f"  Início  : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()
    print("  IMPORTANTE: inicie a captura no Wireshark AGORA,")
    print("  antes de pressionar Enter.")
    print()
    input("  Pressione Enter quando o Wireshark estiver capturando...")
    print()

    # Conecta
    print(f"  Conectando em {host}:{port} ...", end=" ", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect((host, port))
    except Exception as e:
        print(f"\n  ERRO: {e}")
        sys.exit(1)
    print("OK")

    # Envia identificação do grupo (apenas para o log do servidor)
    try:
        ident = json.dumps({"grupo": grupo}) + "\n"
        sock.sendall(ident.encode())
    except Exception as e:
        print(f"\n  ERRO ao enviar identificação: {e}")
        sock.close()
        sys.exit(1)

    # Lê header do servidor
    try:
        sock.settimeout(5.0)
        raw = b""
        while b"\n" not in raw:
            chunk = sock.recv(512)
            if not chunk:
                break
            raw += chunk
        header   = json.loads(raw.split(b"\n")[0])
        duration = header.get("duration", 60)
        print(f"  Sessão confirmada: {int(duration)}s de stream")
        print()
    except Exception as e:
        print(f"\n  ERRO ao ler confirmação: {e}")
        sock.close()
        sys.exit(1)

    # Recebe stream
    sock.settimeout(None)
    total      = 0
    start      = time.time()
    last_t     = start
    last_bytes = 0
    last_recv  = start
    stalled    = False

    print("  Recebendo dados — não feche esta janela.")
    print("  Observe o Wireshark para acompanhar os fenômenos TCP.")
    print()

    try:
        while True:
            now     = time.time()
            elapsed = now - start

            if elapsed > duration + 5:
                break

            stalled = (now - last_recv) > 1.5

            # Atualiza display a cada 1s
            if now - last_t >= 1.0:
                tp = (total - last_bytes) / (now - last_t)
                status = "  *** PAUSA DO SERVIDOR — observe o Wireshark ***" if stalled else ""
                print(
                    f"\r  t={elapsed:5.1f}s | "
                    f"recebido={fmt_bytes(total):>10s} | "
                    f"throughput={fmt_tp(tp):>12s}{status}",
                    end="", flush=True
                )
                last_t     = now
                last_bytes = total

            sock.settimeout(0.5)
            try:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    break
                total     += len(data)
                last_recv  = time.time()
                stalled    = False
            except socket.timeout:
                continue
            except ConnectionResetError:
                break

    except KeyboardInterrupt:
        print("\n\n  Interrompido pelo usuário.")
    finally:
        sock.close()

    # Resumo
    elapsed = time.time() - start
    avg_tp  = total / elapsed if elapsed > 0 else 0

    print("\n")
    print("=" * 60)
    print("  RESUMO DA SESSÃO")
    print("=" * 60)
    print(f"  Duração         : {elapsed:.1f}s")
    print(f"  Total recebido  : {fmt_bytes(total)}")
    print(f"  Throughput médio: {fmt_tp(avg_tp)}")
    print("=" * 60)
    print()
    print("  Próximos passos no Wireshark:")
    print("  1. Pare a captura (Ctrl+E) e salve o .pcap com o nome do grupo")
    print("  2. Statistics → TCP Stream Graph → Time/Sequence (Stevens)")
    print("     Identifique: slow start, platôs e retomadas após cada evento")
    print("  3. Statistics → TCP Stream Graph → Window Scaling")
    print("     Observe a rwnd durante os eventos de pausa")
    print("  4. Filtre retransmissões: tcp.analysis.retransmission")
    print("     Localize retransmissões após cada evento")
    print()


def main():
    parser = argparse.ArgumentParser(description="Cliente TCP — Trabalho de Redes")
    parser.add_argument("--grupo", required=True, help="Ex: GRUPO01")
    parser.add_argument("--host",  default=SERVER_HOST)
    parser.add_argument("--port",  type=int, default=SERVER_PORT)
    args = parser.parse_args()
    run(args.grupo, args.host, args.port)


if __name__ == "__main__":
    main()