import logging
import sys


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """
    Configure application-wide standard Python logging.
    Format: timestamp | level | module | message
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-configuration
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    else:
        root_logger.handlers = [handler]

    # Silence overly verbose third-party loggers if needed
    logging.getLogger("uvicorn.access").setLevel(numeric_level)

    logger = logging.getLogger("yojansetu")
    logger.setLevel(numeric_level)
    return logger
