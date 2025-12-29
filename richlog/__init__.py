import logging
import functools
from logging.handlers import QueueListener
from multiprocessing import Queue

from richlog.handlers import RichExceptionHandler, RichQueueHandler

class RichLogManager:
    """
    A manager class to simplify rich.logging in multiprocess environments.
    """
    def __init__(self, level: str | int, **handler_kwargs):
        self._queue = Queue()
        self._level = level
        self._handler_kwargs = handler_kwargs

    def _set_basic_config(self):
        logging.basicConfig(
            level=self._level,
            format="[bold cyan][%(name)s][/] %(message)s",
            handlers=[RichQueueHandler(self._queue, **self._handler_kwargs)],
        )

    def main_process(self, func):
        """Decorator for main process."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            self._set_basic_config()
            listener = QueueListener(
                self._queue,
                RichExceptionHandler(**self._handler_kwargs)
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
