# trabalho-redes-tcp/client/client.py

import argparse
import logging
import os
import socket
import sys
import time
from typing import Optional

from common.logging_config import setup_logging
from common.opcode import Opcode
from common.protocol import Protocol

setup_logging(name="client")
logger = logging.getLogger("client")

CHUNK_SIZE = 4096

class Client:
    """Encapsula a lógica do cliente para uma sessão interativa com o servidor."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Estabelece a conexão com o servidor."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            logger.info(f"Conectando ao servidor em {self.host}:{self.port}...")
            self.sock.connect((self.host, self.port))
            logger.info("Conexão estabelecida com sucesso. Bem-vindo!")
            return True
        except (ConnectionRefusedError, socket.gaierror, socket.timeout) as e:
            logger.critical(f"Falha ao conectar ao servidor: {e}")
            self.sock = None
            return False

    def close(self):
        """Fecha a conexão do socket."""
        if self.sock:
            self.sock.close()
            self.sock = None
            logger.info("Conexão fechada.")

    def _request_list(self):
        # (Este método permanece o mesmo)
        if not self.sock: return
        self.sock.sendall(Protocol.pack_message(Opcode.LIST))
        try:
            opcode, payload = next(Protocol.unpack_stream(self.sock))
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
        self.sock.sendall(Protocol.pack_message(Opcode.QUIT))
        try:
            opcode, payload = next(Protocol.unpack_stream(self.sock))
            logger.info(f"Resposta do servidor: {payload.decode('utf-8')}")
        except StopIteration:
            logger.info("Conexão fechada pelo servidor.")

    def _request_put(self, filename: str):
        # (Este método permanece essencialmente o mesmo)
        if not self.sock: return
        # ... (código existente para _request_put)
        if not os.path.exists(filename):
            logger.critical(f"Arquivo local não encontrado: '{filename}'")
            return
        
        file_size = os.path.getsize(filename)
        logger.info(f"Solicitando upload do arquivo '{filename}' ({file_size} bytes).")

        self.sock.sendall(Protocol.pack_message(Opcode.PUT, os.path.basename(filename).encode('utf-8')))
        try:
            opcode, payload = next(Protocol.unpack_stream(self.sock))
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
        start_time = time.monotonic()
        try:
            with open(filename, "rb") as f:
                while chunk := f.read(CHUNK_SIZE):
                    self.sock.sendall(Protocol.pack_message(Opcode.DATA_CHUNK, chunk))
            
            self.sock.sendall(Protocol.pack_message(Opcode.END_OF_FILE))

            opcode, payload = next(Protocol.unpack_stream(self.sock))
            if opcode == Opcode.SUCCESS and payload == b"UPLOAD_COMPLETE":
                end_time = time.monotonic()
                logger.info("Transferência concluída com sucesso!")
                self._log_transfer_metrics(file_size, start_time, end_time)
            else:
                logger.error(f"Falha na confirmação final do servidor: {payload.decode('utf-8')}")
        
        except (OSError, StopIteration) as e:
            logger.error(f"Erro durante a transferência do arquivo: {e}")

    def _log_transfer_metrics(self, file_size_bytes: int, start_time: float, end_time: float):
        # (Este método permanece o mesmo)
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
    
    # <<< NOVO: Método principal para o shell interativo >>>
    def start_interactive_session(self):
        """Inicia a conexão e o loop de comandos do cliente."""
        if not self.connect():
            sys.exit(1)
        
        try:
            while True:
                # Exibe o prompt e aguarda a entrada do usuário
                line = input("cliente> ")
                if not line:
                    continue

                parts = line.strip().split()
                command = parts[0].lower()
                args = parts[1:]

                match command:
                    case "list":
                        self._request_list()
                    case "put":
                        if not args:
                            logger.warning("Uso: put <caminho_do_arquivo>")
                            continue
                        self._request_put(args[0])
                    case "quit":
                        self._request_quit()
                        break # Sai do laço while
                    case _:
                        logger.error(f"Comando desconhecido: '{command}'. Comandos disponíveis: list, put, quit.")
        except KeyboardInterrupt:
            print("\nSaindo...")
        finally:
            self.close()

def main():
    """Analisa os argumentos de conexão e inicia a sessão interativa."""
    parser = argparse.ArgumentParser(description="Cliente interativo para serviço de arquivos.")
    parser.add_argument("--host", default="localhost", help="Endereço IP do servidor.")
    parser.add_argument("--port", type=int, default=65432, help="Porta do servidor.")
    args = parser.parse_args()

    client = Client(args.host, args.port)
    client.start_interactive_session()

if __name__ == "__main__":
    main()