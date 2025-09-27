# trabalho-redes-tcp/server/server.py

import logging
import os
import socket
import threading

from common.logging_config import setup_logging
from server.client_handler import ClientHandler

# --- Constantes de Configuração ---
HOST = "0.0.0.0"  # Escuta em todas as interfaces de rede
PORT = 65432  # Porta para escutar (portas > 1023 não requerem privilégios)
UPLOADS_DIR = "server/uploads"

# Configura o logger principal do servidor
setup_logging(name="server")
logger = logging.getLogger("server")


def main():
    """Função principal para iniciar o servidor."""

    # Garante que o diretório de uploads exista
    try:
        os.makedirs(UPLOADS_DIR, exist_ok=True)
        logger.info(f"Diretório de uploads '{UPLOADS_DIR}' está pronto.")
    except OSError as e:
        logger.critical(f"Não foi possível criar o diretório de uploads: {e}")
        return

    # Usar um gerenciador de contexto para garantir que o socket seja fechado
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        # Permite reutilizar o endereço, útil para reinícios rápidos do servidor
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
                # Bloqueia a execução esperando por uma nova conexão
                conn, addr = server_socket.accept()

                # Cria e inicia uma nova thread para lidar com o cliente
                client_thread = ClientHandler(conn, addr, UPLOADS_DIR)
                client_thread.start()

                # Opcional: Logar threads ativas
                logger.debug(f"Threads ativas: {threading.active_count()}")

            except KeyboardInterrupt:
                logger.info("Sinal de interrupção recebido. Desligando o servidor.")
                break
            except Exception as e:
                logger.error(f"Erro ao aceitar conexão: {e}", exc_info=True)


if __name__ == "__main__":
    main()
