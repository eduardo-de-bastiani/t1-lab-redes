from enum import IntEnum


class Opcode(IntEnum):
    """Define os códigos de operação para o protocolo."""

    LIST = 1
    PUT = 2
    QUIT = 3

    SUCCESS = 10
    ERROR = 11

    DATA_CHUNK = 20
    END_OF_FILE = 21
