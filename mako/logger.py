import logging
import sys


class StreamToLogger:
    """
    Fake file-like stream object that redirects writes to a logger instance.
    """

    def __init__(self, logger: logging.Logger, level: int) -> None:
        self.logger = logger
        self.level = level
        self.linebuf = ""

    def write(self, buf: str) -> None:
        for line in buf.rstrip().splitlines():
            self.logger.log(self.level, line.rstrip())

    def flush(self) -> None:
        pass


def make_logger() -> logging.Logger:
    logger = logging.getLogger("mako")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler("mako.log")
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)
    return logger


mako_logger = make_logger()
sys.stdout = StreamToLogger(mako_logger, logging.INFO)
sys.stderr = StreamToLogger(mako_logger, logging.ERROR)
