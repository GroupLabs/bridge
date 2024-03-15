import logging
import os

LOG_LEVEL = "INFO"

def get_log_level_from_str(log_level_str: str = LOG_LEVEL) -> int:
    log_level_dict = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }

    return log_level_dict.get(log_level_str.upper(), logging.INFO)

def setup_logger(
    name: str = __name__,
    logfile_name: str = None,
    log_level: int = logging.INFO,
) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logfile_name:
        logfile_name = name if name else __name__

    if logger.handlers:
        return logger

    logger.setLevel(log_level)

    formatter = logging.Formatter(
        "%(levelname)s: %(asctime)s %(filename)20s%(lineno)4s : %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if logfile_name:
        is_containerized = os.path.exists("/.dockerenv")
        file_name_template = (
            "/var/log/{name}.log" if is_containerized else "./log/{name}.log"
        )

        log_dir = os.path.dirname(file_name_template.format(name=logfile_name))
        os.makedirs(log_dir, exist_ok=True) # create log dir

        file_handler = logging.FileHandler(file_name_template.format(name=logfile_name))
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

if __name__ == "__main__":
    logger = setup_logger(log_level=logging.INFO, logfile_name="test")

    logger.info("Hello world!")
    logger.warning("Thrusters overheating")
    logger.error("Propulsion system not responding")
    logger.critical("System crash!")
