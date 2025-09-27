import logging
import struct

from socket import socket

from common.opcode import Opcode

logger = logging.getLogger(__name__)


class Protocol:
    """
    Gerencia a formatação e o parsing de mensagens do protocolo.

    O frame do protocolo é definido como:
    - 1 byte para o Opcode (código da operação)
    - 8 bytes para o tamanho do payload (dados), como um inteiro sem sinal (unsigned long long)
    - N bytes para o payload (os dados em si)

    Formato do struct: !B Q
    - !: Ordem de bytes da rede (big-endian), padrão para comunicação em rede.
    - B: 1 byte para um inteiro sem sinal (Opcode).
    - Q: 8 bytes para um inteiro sem sinal (tamanho do payload).
    """

    HEADER_FORMAT = "!B Q"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    @staticmethod
    def pack_message(opcode: Opcode, payload: bytes = b"") -> bytes:
        """Empacota uma mensagem no formato do protocolo."""
        payload_size = len(payload)
        header = struct.pack(Protocol.HEADER_FORMAT, opcode.value, payload_size)
        return header + payload

    @staticmethod
    def unpack_stream(sock: socket):
        """
        Gerador que desempacota mensagens de um stream de socket.
        Lê o cabeçalho, determina o tamanho do payload e lê o payload do socket.

        Yields:
            tuple[Opcode, bytes]: Uma tupla contendo o opcode e o payload da mensagem.
        """
        while True:
            try:
                header_data = sock.recv(Protocol.HEADER_SIZE)
                if not header_data:
                    # Conexão fechada pelo peer
                    break

                # Garante que o cabeçalho completo foi recebido
                if len(header_data) < Protocol.HEADER_SIZE:
                    logger.warning("Recebido cabeçalho incompleto. Fechando conexão.")
                    break

                opcode_val, payload_size = struct.unpack(
                    Protocol.HEADER_FORMAT, header_data
                )
                opcode = Opcode(opcode_val)

                payload = b""
                if payload_size > 0:
                    bytes_recebidos = 0
                    chunks = []
                    while bytes_recebidos < payload_size:
                        # Lê em pedaços para não sobrecarregar a memória com arquivos grandes
                        chunk_size = min(4096, payload_size - bytes_recebidos)
                        chunk = sock.recv(chunk_size)
                        if not chunk:
                            logger.error(
                                "Conexão fechada inesperadamente durante o recebimento do payload."
                            )
                            return  # Encerra o gerador
                        chunks.append(chunk)
                        bytes_recebidos += len(chunk)
                    payload = b"".join(chunks)

                yield opcode, payload

            except (struct.error, ValueError) as e:
                logger.error(
                    f"Erro ao desempacotar mensagem: {e}. Descartando e continuando."
                )
                break  # Encerra em caso de erro de protocolo
            except ConnectionResetError:
                logger.warning("Conexão reiniciada pelo peer.")
                break
            except Exception as e:
                logger.critical(f"Erro inesperado no stream de desempacotamento: {e}")
                break
