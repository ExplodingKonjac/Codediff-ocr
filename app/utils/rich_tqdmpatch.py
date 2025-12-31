"""
Do a monkey patch to tqdm in for compatibility with rich.
"""
import sys
import tqdm
import tqdm.auto
import tqdm.std
from tqdm.rich import tqdm as rich_tqdm

class _RichTqdmWrapper(rich_tqdm):
    def __init__(self, *args, **kwargs):
        kwargs.pop("ascii", None)
        super().__init__(*args, **kwargs)

tqdm.auto.tqdm = _RichTqdmWrapper
tqdm.std.tqdm = _RichTqdmWrapper
tqdm.tqdm = _RichTqdmWrapper
sys.modules['tqdm'].tqdm = _RichTqdmWrapper
