# trabalho-redes-tcp/common/opcode.py

from enum import IntEnum


class Opcode(IntEnum):
    """Define os códigos de operação para o protocolo."""

    # Requisições do Cliente
    LIST = 1
    PUT = 2
    QUIT = 3

    # Respostas do Servidor
    SUCCESS = 10
    ERROR = 11

    # Opcodes para streaming de dados
    DATA_CHUNK = 20
    END_OF_FILE = 21
