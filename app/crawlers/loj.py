"""
Module including crawler for LOJ.
"""
import logging
from itertools import count
from typing import Optional, Iterator

import bs4
import requests
from playwright.sync_api import Page
from PIL import Image
from markdownify import MarkdownConverter

from app.crawlers import apply_visual_augmentations, get_screenshot_with_jitter
from app.utils.web import request_retry


class LOJConverter(MarkdownConverter):
    """Convert LOJ statement to markdown"""

    def convert_mjx_container(self,
                              el: bs4.element.Tag,
                              text: str,
                              parent_tags: set[str]) -> str:
        tex = el.get('title')
        assert isinstance(tex, str)
        if el.get('display') == 'true':
            return f"\n\n$$\n{tex.strip()}\n$$\n\n"
        return f"${tex.strip()}$"

    def convert_div(self,
                    el: bs4.element.Tag,
                    text: str,
                    parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if 'header' in class_list:
            if 'large' in class_list:
                return f"\n\n## {text}\n\n"
            if 'small' in class_list:
                return f"\n\n### {text}\n\n"
        return getattr(super(), "convert_div")(el, text, parent_tags)

    def convert_a(self,
                  el: bs4.element.Tag,
                  text: str,
                  parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if '_copySample_1rcs8_202' in class_list:
            return ""
        return getattr(super(), "convert_a")(el, text, parent_tags)


def crawl_problem(page: Page, *,
                  problem_id: str,
                  contest_id: Optional[str] = None) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id in LOJ

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in LOJ.
        contest_id (str): Not used, for compatibility with other crawlers.

    Returns:
        tuple[Image.Image, str]: A tuple of (image, description)
    """

    page.goto(f"https://loj.ac/p/{problem_id}")
    page.wait_for_load_state('networkidle')

    statement = page.locator('._leftContainer_1rcs8_1').first
    if not statement.is_visible():
        raise RuntimeError("Problem statement not found")

    # remove default font preference
    page.evaluate("""
        document.getElementById("font-preference-content").remove()
        document.getElementById("font-ui").remove()
    """)

    # visual augmentation
    apply_visual_augmentations(page, statement)

    # take screenshot
    image = get_screenshot_with_jitter(page, statement)

    # get description
    converter = LOJConverter(heading_style='ATX')
    description = converter.convert(statement.inner_html())

    return image, description

def fetch_problem_list() -> Iterator[tuple[str, Optional[str]]]:
    """
    Fetch problem list from LOJ.

    Yields:
        tuple[str, Optional[str]]: A tuple of (problem_id, contest_id)
    """
    logger = logging.getLogger("Fetcher")
    page_delta = 100
    for page in count(0, page_delta):
        resp = request_retry(5, lambda: requests.post(
            'https://api.loj.ac/api/problem/queryProblemSet',
            json={'locale': 'zh_CN', 'skipCount': page, 'takeCount': page_delta},
            timeout=5,
        ), lambda e, retry_count: logger.exception(
            "Failed to fetch problem list from LOJ: %s, retrying (%d)...",
            repr(e), retry_count
        ))
        if resp is None:
            logger.error("Failed to fetch page %d to %d from LOJ", page, page + page_delta)
        else:
            try:
                info_list = resp.json()['result']
                if len(info_list) == 0:
                    break
                for problem_info in info_list:
                    yield (str(problem_info['meta']['displayId']), None)
            except Exception:
                logger.exception("Failed to process data: %s", resp.text)
