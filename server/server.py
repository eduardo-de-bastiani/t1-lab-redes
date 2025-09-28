import logging
import os
import socket
import threading

from common.logging_config import setup_logging
from server.client_handler import ClientHandler


HOST = "0.0.0.0"
PORT = 65432
UPLOADS_DIR = "server/uploads"


setup_logging(name="server")
logger = logging.getLogger("server")


def main():
    """Função principal para iniciar o servidor."""

    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        logger.info(f"Diretório de uploads '{UPLOADS_DIR}' está pronto.")
    except OSError as e:
        logger.critical(f"Não foi possível criar o diretório de uploads: {e}")
        return

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:

        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server_socket.bind((HOST, PORT))
            server_socket.listen()
            logger.info(f"Servidor escutando em {HOST}:{PORT}")
        except OSError as e:
            logger.critical(f"Falha ao iniciar o servidor em {HOST}:{PORT}. Erro: {e}")
            return

        while True:
            try:

                conn, addr = server_socket.accept()

                client_thread = ClientHandler(conn, addr, UPLOADS_DIR)
                client_thread.start()

                logger.debug(f"Threads ativas: {threading.active_count()}")

            except KeyboardInterrupt:
                logger.info("Sinal de interrupção recebido. Desligando o servidor.")
                break
            except Exception as e:
                logger.error(f"Erro ao aceitar conexão: {e}", exc_info=True)


if __name__ == "__main__":
    main()
