import logging
import sys


def setup_logging(level=logging.INFO, name: str = "app"):
    """
    Configura o logging básico para a aplicação.

    Args:
        level: O nível de logging (e.g., logging.INFO, logging.DEBUG).
        name: O nome do logger principal (geralmente 'client' ou 'server').
    """

    log_format = f"%(asctime)s - {name.upper()} - [%(levelname)s] - %(name)s - (%(filename)s:%(lineno)d) - %(message)s"

    logging.basicConfig(
        level=level, format=log_format, handlers=[logging.StreamHandler(sys.stdout)]
    )

    logger = logging.getLogger(name)
    logger.info("Sistema de logging inicializado.")
