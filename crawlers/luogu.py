"""
Module including crawler for Luogu.
"""
import time
import logging
from typing import Optional, Iterator
from itertools import count

import requests
from playwright.sync_api import Page
from PIL import Image

from crawlers import apply_visual_augmentations, get_screenshot_with_jitter
from utils.web import USER_AGENT, request_retry

def crawl_problem(page: Page, *,
                  problem_id: str,
                  contest_id: Optional[str] = None) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id from Luogu

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in Luogu.
        contest_id (str): Not used, for compatibility with other crawlers.
    
    Returns:
        tuple[Image.Image, str]: A tuple of (image, description)
    """

    page.goto(f'https://www.luogu.com.cn/problem/{problem_id}')
    page.wait_for_load_state('networkidle')

    # get statement element
    statement = page.locator('.problem').first
    if not statement.is_visible():
        raise RuntimeError("Problem statement not found")

    # visual augmentation
    apply_visual_augmentations(page, statement)

    # take screenshot
    image = get_screenshot_with_jitter(page, statement)

    # get description
    copy_btn = page.locator('.problem-block-actions').get_by_text('Markdown').first
    if not copy_btn.is_visible():
        raise RuntimeError("Copy button not found")

    copy_btn.click()
    time.sleep(0.1)
    description: str = page.evaluate('navigator.clipboard.readText()')

    description = description[description.index('\n\n') + 2:]
    return image, description

def fetch_problem_list() -> Iterator[tuple[str, Optional[str]]]:
    """
    Fetch problem list from Luogu.

    Yields:
        tuple[str, Optional[str]]: A tuple of (problem_id, contest_id)
    """
    logger = logging.getLogger("Fetcher")
    total_num = 0

    for problem_type in ('P', 'B'):
        logger.info("Fetching problemset '%s'...", problem_type)
        for page in count(0):
            resp = request_retry(5, lambda: requests.get(
                "https://www.luogu.com.cn/problem/list",
                params={'page': page, 'type': problem_type},
                headers={'x-lentille-request': 'content-only', 'user-agent': USER_AGENT},
                timeout=5
            ), lambda retry_count, e: logger.exception(
                "Failed to fetch problem list from Luogu: %s, retrying (%d)...",
                repr(e), retry_count
            ))
            if resp is None:
                logger.error(
                    "Failed to fetch page %d of problem type %s from Luogu",
                    page, problem_type
                )
            else:
                data = resp.json()['data']['problems']
                for problem in data['result']:
                    yield (problem['pid'], None)
                total_num += data['perPage']
                if total_num >= data['count']:
                    break
