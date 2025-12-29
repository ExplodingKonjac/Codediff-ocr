from traceback import print_tb
import logging
from logging.handlers import QueueHandler
from multiprocessing import Queue

from rich.logging import RichHandler
from rich.console import Group
from rich.traceback import Traceback


class RichExceptionHandler(RichHandler):
    """Add traceback to log record."""

    def render_message(self, record: logging.LogRecord, message):
        if e := getattr(record, 'rich_traceback', None):
            return Group(message, e)
        return super().render_message(record, message)


class RichQueueHandler(QueueHandler):
    """Add traceback to log record."""

    def __init__(self, queue: Queue, rich_tracebacks: bool, **tracebacks_config) -> None:
        super().__init__(queue)
        self.rich_tracebacks = rich_tracebacks
        self.tracebacks_config = {
            k.removeprefix('tracebacks_'): v
            for k, v in tracebacks_config.items()
            if k.startswith('tracebacks_')
        }

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        if (
            self.rich_tracebacks and
            record.exc_info and
            record.exc_info != (None, None, None)
        ):
            exc_type, exc_value, exc_traceback = record.exc_info
            assert exc_type is not None
            assert exc_value is not None
            record.rich_traceback = Traceback.from_exception(
                exc_type,
                exc_value,
                exc_traceback,
                **self.tracebacks_config,
            )
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
        record.msg = self.format(record)
        record.args = None
        return record
