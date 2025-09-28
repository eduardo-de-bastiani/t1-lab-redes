import logging
import os
import threading
from socket import socket

from common.opcode import Opcode
from common.protocol import Protocol

logger = logging.getLogger(__name__)


class ClientHandler(threading.Thread):
    """
    Gerencia a comunicação com um cliente conectado em uma thread separada.
    """

    def __init__(self, conn: socket, addr: tuple, uploads_dir: str):
        super().__init__(daemon=True)
        self.conn = conn
        self.addr = addr
        self.uploads_dir = uploads_dir
        self.is_running = True
        self.name = f"Thread-{addr[0]}:{addr[1]}"

    def _handle_list(self):
        """Lida com a requisição LIST."""
        logger.info(f"Cliente {self.addr} solicitou a lista de arquivos.")
        try:
            files = os.listdir(self.uploads_dir)
            file_list_str = "\n".join(files)
            if not file_list_str:
                file_list_str = "Nenhum arquivo no servidor."
            response_payload = file_list_str.encode("utf-8")
            self.conn.sendall(Protocol.pack_message(Opcode.SUCCESS, response_payload))
        except FileNotFoundError:
            logger.error(
                f"O diretório de uploads '{self.uploads_dir}' não foi encontrado."
            )
            error_msg = "Erro interno no servidor: diretório de uploads não encontrado."
            self.conn.sendall(
                Protocol.pack_message(Opcode.ERROR, error_msg.encode("utf-8"))
            )

    def _handle_quit(self):
        """Lida com a requisição QUIT."""
        logger.info(f"Cliente {self.addr} solicitou o encerramento da conexão.")
        try:
            self.conn.sendall(Protocol.pack_message(Opcode.SUCCESS, b"Adeus!"))
        except OSError:
            pass
        finally:
            self.is_running = False

    def _handle_put(self, initial_payload: bytes):
        """Lida com a requisição PUT para fazer upload de um arquivo."""

        try:
            filename = initial_payload.decode("utf-8")
            safe_filename = os.path.basename(filename)
            filepath = os.path.join(self.uploads_dir, safe_filename)

            logger.info(
                f"Cliente {self.addr} solicitou o upload do arquivo: {safe_filename}"
            )

            if os.path.exists(filepath):
                logger.warning(
                    f"Upload negado: arquivo '{safe_filename}' já existe no servidor."
                )
                error_msg = f"Arquivo '{safe_filename}' já existe.".encode("utf-8")
                self.conn.sendall(Protocol.pack_message(Opcode.ERROR, error_msg))
                return

            logger.debug(
                f"Sinalizando para o cliente {self.addr} que pode enviar o arquivo."
            )
            self.conn.sendall(Protocol.pack_message(Opcode.SUCCESS, b"OK_TO_SEND"))

            with open(filepath, "wb") as f:
                for opcode, payload in Protocol.unpack_stream(self.conn):
                    if opcode == Opcode.DATA_CHUNK:
                        f.write(payload)
                    elif opcode == Opcode.END_OF_FILE:
                        logger.info(
                            f"Transferência do arquivo '{safe_filename}' de {self.addr} concluída."
                        )
                        self.conn.sendall(
                            Protocol.pack_message(Opcode.SUCCESS, b"UPLOAD_COMPLETE")
                        )
                        return
                    else:
                        logger.error(
                            f"Protocolo inesperado durante o upload de {self.addr}: {opcode}"
                        )
                        raise ConnectionResetError(
                            "Erro de protocolo durante o upload."
                        )
        except Exception as e:
            logger.error(
                f"Erro durante o upload do arquivo de {self.addr}: {e}", exc_info=True
            )
            if "filepath" in locals() and os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Arquivo parcial '{safe_filename}' removido.")
            try:
                self.conn.sendall(
                    Protocol.pack_message(Opcode.ERROR, str(e).encode("utf-8"))
                )
            except OSError:
                pass
            self.is_running = False

    def run(self):
        """
        Método principal da thread. Escuta por múltiplos comandos até que QUIT seja recebido.
        """
        logger.info(f"Conexão de {self.addr} estabelecida. Aguardando comandos.")
        try:

            for opcode, payload in Protocol.unpack_stream(self.conn):

                match opcode:
                    case Opcode.LIST:
                        self._handle_list()
                    case Opcode.PUT:
                        self._handle_put(payload)
                    case Opcode.QUIT:
                        self._handle_quit()

                if not self.is_running:
                    break

        except (ConnectionResetError, StopIteration):
            logger.warning(
                f"Conexão com {self.addr} foi fechada abruptamente pelo cliente."
            )
        except Exception as e:
            logger.error(
                f"Erro crítico na comunicação com {self.addr}: {e}", exc_info=True
            )
        finally:
            logger.info(f"Encerrando sessão e conexão com {self.addr}.")
            self.conn.close()
