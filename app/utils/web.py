"""
Utils for web related tasks.
"""
import time
from typing import Optional, Callable

import requests

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' \
             'AppleWebKit/537.36 (KHTML, like Gecko) ' \
             'Chrome/143.0.0.0 ' \
             'Safari/537.36 ' \
             'Edg/143.0.0.0'

def request_retry(count: int,
                  req_func: Callable[[], requests.Response],
                  log_func: Callable[[int, Exception], None]) -> Optional[requests.Response]:
    """
    Retry a request with a given count.

    Args:
        count (int): The number of retries.
        req_func (Callable[[], requests.Response]): The function to call.
        log_func (Callable[[int], None]): The function to log.

    Returns:
        Optional[requests.Response]: The response if successful, None otherwise.
    """
    for _ in range(count):
        try:
            resp = req_func()
            resp.raise_for_status()
            return resp
        except Exception as e:
            log_func(_ + 1, e)
            time.sleep(1)
    return None
