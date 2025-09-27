# trabalho-redes-tcp/client/client.py

import argparse
import logging
import os
import socket
import struct
import sys
import threading
import time
from datetime import datetime
from typing import Optional

from common.logging_config import setup_logging
from common.opcode import Opcode
from common.protocol import Protocol

setup_logging(name="client")
logger = logging.getLogger("client")

CHUNK_SIZE = 4096
TCP_INFO_FORMAT = "B" * 4 + "I" * 10 + "Q" * 8 # Formato aproximado para decodificar tcp_info

class Client:
    """Encapsula a lógica do cliente para uma sessão interativa com o servidor."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        # <<< NOVO: Atributos para métricas da sessão >>>
        self.session_start_time: Optional[float] = None
        self.session_end_time: Optional[float] = None
        self.bytes_sent = 0
        self.bytes_received = 0
        self.tcp_info_log = []
        self.tcp_info_collector_thread: Optional[threading.Thread] = None
        self.stop_tcp_info_collector = threading.Event()

    # <<< NOVO: Wrapper para sendall para contar bytes enviados >>>
    def _send(self, data: bytes):
        if not self.sock: return
        try:
            self.sock.sendall(data)
            self.bytes_sent += len(data)
        except OSError as e:
            logger.error(f"Erro ao enviar dados: {e}")
            raise

    # <<< NOVO: Wrapper para o gerador unpack_stream para contar bytes recebidos >>>
    def _recv_stream(self):
        if not self.sock: return
        for opcode, payload in Protocol.unpack_stream(self.sock):
            # O cabeçalho (9 bytes) + payload
            self.bytes_received += Protocol.HEADER_SIZE + len(payload)
            yield opcode, payload

    def _start_tcp_info_collector(self):
        """Inicia uma thread para coletar dados TCP_INFO periodicamente."""
        if not sys.platform.startswith('linux'):
            logger.info("Coleta de TCP_INFO não é suportada neste SO. Pulando.")
            return

        def collector():
            while not self.stop_tcp_info_collector.is_set():
                try:
                    # TCP_INFO é o 11º socket option no nível IPPROTO_TCP
                    tcp_info_raw = self.sock.getsockopt(socket.IPPROTO_TCP, socket.TCP_INFO, 104)
                    # Decodifica os campos relevantes (isso pode variar entre kernels)
                    # tcpi_rtt, tcpi_snd_cwnd, tcpi_retrans
                    rtt = struct.unpack_from("=I", tcp_info_raw, 40)[0] / 1000 # RTT em ms
                    cwnd = struct.unpack_from("=I", tcp_info_raw, 24)[0]
                    retrans = struct.unpack_from("=I", tcp_info_raw, 48)[0]
                    self.tcp_info_log.append({
                        "timestamp": time.time(),
                        "rtt_ms": rtt,
                        "cwnd": cwnd,
                        "retransmissions": retrans
                    })
                except (OSError, struct.error) as e:
                    logger.debug(f"Não foi possível coletar TCP_INFO: {e}")
                
                time.sleep(1) # Coleta a cada 1 segundo

        self.stop_tcp_info_collector.clear()
        self.tcp_info_collector_thread = threading.Thread(target=collector, daemon=True)
        self.tcp_info_collector_thread.start()
        logger.info("Coletor de métricas TCP (tcp_info) iniciado.")

    def _stop_tcp_info_collector(self):
        """Para a thread de coleta de TCP_INFO."""
        if self.tcp_info_collector_thread and self.tcp_info_collector_thread.is_alive():
            self.stop_tcp_info_collector.set()
            self.tcp_info_collector_thread.join(timeout=1)
            logger.info("Coletor de métricas TCP (tcp_info) finalizado.")

    def connect(self) -> bool:
        """Estabelece a conexão com o servidor."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.session_start_time = time.monotonic() # Marca o início da sessão
            logger.info(f"Conectando ao servidor em {self.host}:{self.port}...")
            self.sock.connect((self.host, self.port))
            logger.info("Conexão estabelecida com sucesso. Bem-vindo!")
            return True
        except (ConnectionRefusedError, socket.gaierror, socket.timeout) as e:
            logger.critical(f"Falha ao conectar ao servidor: {e}")
            self.sock = None
            return False

    def close(self):
        """Fecha a conexão do socket e gera o log da sessão."""
        if self.sock:
            self.sock.close()
            self.sock = None
            self.session_end_time = time.monotonic()
            logger.info("Conexão fechada.")
            self._create_session_log()

    def _request_list(self):
        if not self.sock: return
        self._send(Protocol.pack_message(Opcode.LIST))
        try:
            opcode, payload = next(self._recv_stream())
            if opcode == Opcode.SUCCESS:
                print("--- Arquivos no Servidor ---\n"
                      f"{payload.decode('utf-8')}\n"
                      "--------------------------")
            else:
                logger.error(f"Servidor retornou um erro: {payload.decode('utf-8')}")
        except StopIteration:
            logger.error("O servidor fechou a conexão inesperadamente.")

    def _request_quit(self):
        if not self.sock: return
        logger.info("Enviando solicitação para encerrar a sessão...")
        self._send(Protocol.pack_message(Opcode.QUIT))
        try:
            opcode, payload = next(self._recv_stream())
            logger.info(f"Resposta do servidor: {payload.decode('utf-8')}")
        except StopIteration:
            logger.info("Conexão fechada pelo servidor.")

    def _request_put(self, filename: str):
        if not self.sock: return
        if not os.path.exists(filename):
            logger.critical(f"Arquivo local não encontrado: '{filename}'")
            return
        
        file_size = os.path.getsize(filename)
        logger.info(f"Solicitando upload do arquivo '{filename}' ({file_size} bytes).")

        self._send(Protocol.pack_message(Opcode.PUT, os.path.basename(filename).encode('utf-8')))
        try:
            opcode, payload = next(self._recv_stream())
            if opcode == Opcode.ERROR:
                logger.error(f"Servidor negou o upload: {payload.decode('utf-8')}")
                return
            if opcode != Opcode.SUCCESS or payload != b"OK_TO_SEND":
                logger.error("Resposta inesperada do servidor. Abortando upload.")
                return
        except StopIteration:
            logger.error("Servidor fechou a conexão antes de confirmar o upload.")
            return

        logger.info("Servidor confirmou. Iniciando transferência...")
        self._start_tcp_info_collector() # Inicia o coletor de tcp_info
        start_time = time.monotonic()
        try:
            with open(filename, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    self._send(Protocol.pack_message(Opcode.DATA_CHUNK, chunk))
            
            self._send(Protocol.pack_message(Opcode.END_OF_FILE))

            opcode, payload = next(self._recv_stream())
            if opcode == Opcode.SUCCESS and payload == b"UPLOAD_COMPLETE":
                end_time = time.monotonic()
                logger.info("Transferência concluída com sucesso!")
                self._log_transfer_metrics(file_size, start_time, end_time)
            else:
                logger.error(f"Falha na confirmação final do servidor: {payload.decode('utf-8')}")
        
        except (OSError, StopIteration) as e:
            logger.error(f"Erro durante a transferência do arquivo: {e}")
        finally:
            self._stop_tcp_info_collector() # Para o coletor ao final da transferência

    def _log_transfer_metrics(self, file_size_bytes: int, start_time: float, end_time: float):
        duration = end_time - start_time
        if duration == 0: duration = 1e-9
        rate_bytes_per_sec = file_size_bytes / duration
        rate_kb_per_sec = rate_bytes_per_sec / 1024
        rate_mb_per_sec = rate_kb_per_sec / 1024
        logger.info("--- Métricas da Transferência ---\n"
                    f"Tamanho Total: {file_size_bytes / 1024:.2f} KB\n"
                    f"Duração: {duration:.4f} segundos\n"
                    f"Taxa de Transferência: {rate_mb_per_sec:.2f} MB/s ({rate_kb_per_sec:.2f} KB/s)\n"
                    "---------------------------------")
    
    def _create_session_log(self):
        """Cria um arquivo de log com as estatísticas consolidadas da sessão."""
        if not self.session_start_time or not self.session_end_time:
            return

        log_dir = "client/logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = os.path.join(log_dir, f"session_{timestamp_str}.log")

        duration = self.session_end_time - self.session_start_time
        avg_rate = (self.bytes_sent + self.bytes_received) / duration if duration > 0 else 0

        with open(log_filename, "w") as f:
            f.write("--- Log da Sessão ---\n")
            f.write(f"Timestamp Início: {datetime.fromtimestamp(time.time() - duration).isoformat()}\n")
            f.write(f"Timestamp Fim: {datetime.now().isoformat()}\n")
            f.write(f"Duração Total: {duration:.4f} segundos\n")
            f.write(f"Total de Bytes Enviados: {self.bytes_sent} bytes\n")
            f.write(f"Total de Bytes Recebidos: {self.bytes_received} bytes\n")
            f.write(f"Taxa Média de Transferência: {avg_rate / 1024:.2f} KB/s\n\n")

            if self.tcp_info_log:
                f.write("--- Métricas TCP (getsockopt(TCP_INFO)) ---\n")
                f.write("timestamp, rtt_ms, cwnd, retransmissions\n")
                for entry in self.tcp_info_log:
                    ts = datetime.fromtimestamp(entry['timestamp']).strftime('%H:%M:%S')
                    f.write(f"{ts}, {entry['rtt_ms']:.3f}, {entry['cwnd']}, {entry['retransmissions']}\n")

        logger.info(f"Log da sessão salvo em: {log_filename}")

    def start_interactive_session(self):
        """Inicia a conexão e o loop de comandos do cliente."""
        if not self.connect():
            sys.exit(1)
        
        try:
            while True:
                line = input("cliente> ")
                if not line: continue
                parts = line.strip().split()
                command = parts[0].lower()
                args = parts[1:]
                match command:
                    case "list": self._request_list()
                    case "put":
                        if not args: logger.warning("Uso: put <caminho_do_arquivo>"); continue
                        self._request_put(args[0])
                    case "quit": self._request_quit(); break
                    case _: logger.error(f"Comando desconhecido: '{command}'.")
        except KeyboardInterrupt:
            print("\nSaindo...")
        finally:
            self.close()

def main():
    parser = argparse.ArgumentParser(description="Cliente interativo para serviço de arquivos.")
    parser.add_argument("--host", default="localhost", help="Endereço IP do servidor.")
    parser.add_argument("--port", type=int, default=65432, help="Porta do servidor.")
    args = parser.parse_args()
    client = Client(args.host, args.port)
    client.start_interactive_session()

if __name__ == "__main__":
    main()