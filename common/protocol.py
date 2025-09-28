import logging
import struct
from socket import socket

from common.opcode import Opcode

logger = logging.getLogger(__name__)


def _recv_all(sock: socket, n_bytes: int) -> bytes | None:
    """
    Recebe exatamente n_bytes de um socket.
    Retorna os dados ou None se a conexão for fechada antes de receber tudo.
    """
    chunks = []
    bytes_received = 0
    while bytes_received < n_bytes:
        try:
            chunk = sock.recv(n_bytes - bytes_received)
            if not chunk:

                return None
            chunks.append(chunk)
            bytes_received += len(chunk)
        except OSError:
            return None
    return b"".join(chunks)


class Protocol:
    HEADER_FORMAT = "!B Q"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    @staticmethod
    def pack_message(opcode: Opcode, payload: bytes = b"") -> bytes:
        payload_size = len(payload)
        header = struct.pack(Protocol.HEADER_FORMAT, opcode.value, payload_size)
        return header + payload

    @staticmethod
    def unpack_stream(sock: socket):
        """
        Gerador robusto que desempacota mensagens de um stream de socket.
        Agora usa _recv_all para evitar erros de leitura parcial ('short reads').
        """
        while True:
            try:

                header_data = _recv_all(sock, Protocol.HEADER_SIZE)
                if header_data is None:

                    logger.warning(
                        "Conexão fechada ao tentar ler o cabeçalho da mensagem."
                    )
                    break

                opcode_val, payload_size = struct.unpack(
                    Protocol.HEADER_FORMAT, header_data
                )
                opcode = Opcode(opcode_val)

                payload = b""
                if payload_size > 0:
                    recv_result = _recv_all(sock, payload_size)
                    if recv_result is None:
                        logger.error(
                            "Conexão fechada inesperadamente durante o recebimento do payload."
                        )
                        break
                    payload = recv_result

                yield opcode, payload

            except (struct.error, ValueError) as e:
                logger.error(
                    f"Erro ao desempacotar mensagem: {e}. Descartando e continuando."
                )
                break
            except ConnectionResetError:
                logger.warning("Conexão reiniciada pelo peer.")
                break
            except Exception as e:
                logger.critical(f"Erro inesperado no stream de desempacotamento: {e}")
                break
