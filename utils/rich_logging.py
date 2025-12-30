"""
Configures rich logging for multiprocess environments.
"""
import logging
import functools
from logging.handlers import QueueHandler, QueueListener
from multiprocessing import Queue

from rich.logging import RichHandler
from rich.console import Group
from rich.traceback import Traceback


class _RichExceptionHandler(RichHandler):
    def render_message(self, record: logging.LogRecord, message):
        if e := getattr(record, 'rich_traceback', None):
            return Group(message, e)
        return super().render_message(record, message)


class _RichQueueHandler(QueueHandler):
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


class RichLogManager:
    """
    A manager class to simplify rich.logging in multiprocess environments.
    """
    def __init__(self, level: str | int, **handler_kwargs):
        self._queue = Queue()
        self._level = level
        handler_kwargs.setdefault('log_time_format', "[%X]")
        handler_kwargs.setdefault('markup', True)
        handler_kwargs.setdefault('omit_repeated_times', False)
        handler_kwargs.setdefault('show_path', False)
        handler_kwargs.setdefault('rich_tracebacks', True)
        self._handler_kwargs = handler_kwargs

    def _set_basic_config(self):
        # basic logging config
        logging.basicConfig(
            level=self._level,
            format="[bold cyan][%(name)s][/] %(message)s",
            handlers=[_RichQueueHandler(self._queue, **self._handler_kwargs)],
            force=True,
        )

        # set transformers logging
        import transformers
        import huggingface_hub
        transformers.logging.disable_default_handler()
        for name in ('transformers', 'huggingface_hub'):
            logger = logging.getLogger(name)
            logger.handlers = []
            logger.addHandler(RichHandler(**self._handler_kwargs))
            logger.propagate = False

    def main_process(self, func):
        """Decorator for main process."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self._set_basic_config()
            listener = QueueListener(
                self._queue,
                _RichExceptionHandler(**self._handler_kwargs)
            )
            listener.start()
            try:
                return func(*args, **kwargs)
            finally:
                listener.stop()
        return wrapper

    def sub_process(self, func):
        """Decorator for sub process."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self._set_basic_config()
            return func(*args, **kwargs)
        return wrapper
