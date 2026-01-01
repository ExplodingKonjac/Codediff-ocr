import io
import random
import time
from typing import Literal, Optional, Iterator
from importlib import import_module

from playwright.sync_api import Page, Locator
from PIL import Image

OJNames = Literal['accoding', 'atcoder', 'codeforces', 'loj', 'luogu']

_crawler_cache = {}

def apply_visual_augmentations(page: Page, locator: Locator):
    """
    Apply visual augmentations to a page.

    Args:
        page (Page): The page to apply augmentations to.
        locator (Locator): The locator to apply augmentations to.
    """

    # resize viewport
    width = random.randint(1000, 2000)
    page.set_viewport_size({"width": width, "height": 1080})

    # inject css
    font_pool_en: dict[str, list[str]] = {
        'sans-serif': [
            'Arial', 'Segoe UI', 'Verdana', 'Tahoma', 'Microsoft Sans Serif',
            'DejaVu Sans', 'Liberation Sans', 'Ubuntu', 'FreeSans', 'Noto Sans',
        ],
        'serif': [
            'Times New Roman', 'Georgia', 'Palatino Linotype', 'DejaVu Serif',
            'Liberation Serif', 'FreeSerif', 'Noto Serif',
        ],
        'monospace': [
            'Courier New', 'Consolas', 'Lucida Console', 'DejaVu Sans Mono',
            'Liberation Mono', 'FreeMono', 'Noto Mono', 'Ubuntu Mono',
        ],
        'cursive': [
            'Comic Sans',
        ]
    }
    font_pool_zh: dict[str, list[str]] = {
        'sans-serif': [
            'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
        ],
        'serif': [
            'SimSun', 'NSimSun', 'Noto Serif CJK SC', 'AR PL UMing CN', 
        ],
        'monospace': [
            'Microsoft YaHei', 'Noto Sans CJK SC', 'SimSun',  'Noto Serif CJK SC',
        ],
        'cursive': [
            'KaiTi', 'FangSong', 'AR PL UKai CN',
        ]
    }

    category = random.choices(
        ['sans-serif', 'serif', 'monospace', 'cursive'],
        weights=[0.5, 0.3, 0.15, 0.05],
        k=1
    )[0]
    random.shuffle(font_pool_en[category])
    random.shuffle(font_pool_zh[category])

    font_family = ', '.join([
        *map(lambda s: "'" + s + "'", font_pool_en[category]),
        *map(lambda s: "'" + s + "'", font_pool_zh[category]),
        category
    ])
    font_size = random.choice(['12px', '14px', '16px', '18px'])
    line_height = random.choice(['1.0', '1.2', '1.5', '1.8'])

    locator.evaluate(f"""
    el => {{
        el.style.setProperty("font-family", "{font_family}", "important");
        el.style.setProperty("font-size", "{font_size}", "important");
        el.style.setProperty("line-height", "{line_height}", "important");
    }}
    """)

    # adjust height
    new_height = page.evaluate("document.body.scrollHeight")
    page.set_viewport_size({"width": width, "height": new_height})
    time.sleep(0.2)

def get_screenshot_with_jitter(page: Page, locator: Locator) -> Image.Image:
    """
    Get screenshot of a locator with a random jitter of borders.

    Args:
        page (Page): The page to take screenshot from.
        locator (Locator): The locator to take screenshot of.

    Returns:
        Image.Image: The screenshot of the locator.
    """
    rect = locator.bounding_box()
    if rect is None:
        raise RuntimeError("Failed to get bounding box")

    left = rect['x']
    top = rect['y']
    right = rect['x'] + rect['width']
    bottom = rect['y'] + rect['height']
    paddings = locator.evaluate("""
    el => {
        const style = window.getComputedStyle(el);
        return {
            top: parseInt(style.paddingTop),
            right: parseInt(style.paddingRight),
            bottom: parseInt(style.paddingBottom),
            left: parseInt(style.paddingLeft)
        }
    }
    """)

    max_extra = 50.0
    left += random.uniform(-max_extra, paddings['left'])
    top += random.uniform(-max_extra, paddings['top'])
    right += random.uniform(-paddings['right'], max_extra)
    bottom += random.uniform(-paddings['bottom'], max_extra)

    image_bytes = page.screenshot(clip={
        'x': left,
        'y': top,
        'width': right - left,
        'height': bottom - top
    })
    return Image.open(io.BytesIO(image_bytes))

def crawl_problem(page: Page,
                  oj: OJNames,
                  *,
                  problem_id: str,
                  contest_id: Optional[str] = None) -> tuple[Image.Image, str]:
    """
    Crawl a problem from a specific OJ.

    Args:
        oj (Literal['accoding', 'atcoder', 'codeforces', 'loj', 'luogu']): The OJ to crawl from.
        problem_id (str): The problem ID to crawl.
        contest_id (str): The contest ID to crawl.

    Returns:
        tuple[Image.Image, str]: The crawled problem image and description.
    """

    m = _crawler_cache.get(oj)
    if m is None:
        m = import_module(f"app.crawlers.{oj}")
        _crawler_cache[oj] = m
    return m.crawl_problem(page, problem_id=problem_id, contest_id=contest_id)

def fetch_problem_list(oj: OJNames) -> Iterator[tuple[str, Optional[str]]]:
    """
    Fetch problem list from a specific OJ.

    Args:
        oj (OJNames): The OJ to fetch from.

    Yields:
        tuple[str, Optional[str]]: A tuple of (problem_id, contest_id).
    """
    m = _crawler_cache.get(oj)
    if m is None:
        m = import_module(f"app.crawlers.{oj}")
        _crawler_cache[oj] = m
    return m.fetch_problem_list()
