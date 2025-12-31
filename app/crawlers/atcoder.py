"""
Module including crawler for atcoder.
"""
import re
import logging
from typing import Iterator, Optional

import bs4
import requests
from playwright.sync_api import Page
from PIL import Image
from markdownify import MarkdownConverter

from app.crawlers import apply_visual_augmentations, get_screenshot_with_jitter
from app.utils.web import request_retry


class AtCoderConverter(MarkdownConverter):
    """Convert AtCoder statement to Markdown"""

    def convert_span(self,
                     el: bs4.element.Tag,
                     text: str,
                     parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if el.get('id') == 'task-lang-btn':
            return ''
        if 'btn-copy' in class_list:
            return ''
        if 'katex-display' in class_list:
            annotation = el.find('annotation')
            assert annotation is not None
            return f"\n\n$$\n{annotation.get_text()}\n$$\n\n"
        if 'katex' in class_list:
            annotation = el.find('annotation')
            assert annotation is not None
            return f"${annotation.get_text()}$"
        if 'h2' in class_list:
            return f"\n\n# {text.strip()}\n\n"
        return text

    def convert_a(self,
                  el: bs4.element.Tag,
                  text: str,
                  parent_tags: set[str]) -> str:
        if 'btn' in el.get_attribute_list('class'):
            return ''
        return getattr(super(), "convert_a")(el, text, parent_tags)

    def convert_hN(self,
                   n: int,
                   el: bs4.element.Tag,
                   text: str,
                   parent_tags: set[str]) -> str:
        return getattr(super(), 'convert_hN')(n - 1, el, text, parent_tags)


def crawl_problem(page: Page, *,
                  problem_id: str,
                  contest_id: str) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id from AtCoder

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in AtCoder.
        contest_id (str): Contest ID in AtCoder.

    Returns:
        tuple[Image.Image, str]: A tuple of (image, description)
    """

    page.goto(f"https://atcoder.jp/contests/{contest_id}/tasks/{problem_id}")
    page.wait_for_load_state("networkidle")

    # locate statement element
    statement = page.locator('#task-statement').first.locator('xpath=..')
    if not statement.is_visible():
        raise RuntimeError("Problem statement not found")

    # remove invisible elements
    statement.evaluate("""
    el => {
        el.querySelectorAll('*').forEach(el => {
            if (el.tagName.toLowerCase() === 'annotation') {
                return;
            }
            const style = window.getComputedStyle(el);
            if (el.tagName.toLowerCase() === 'form' ||
                style.display === 'none' ||
                style.visibility === 'hidden' ||
                style.opacity === '0') {
                el.remove();
            }
        });
    }
    """)

    # visual augmentation
    apply_visual_augmentations(page, statement)

    # take screenshot
    image = get_screenshot_with_jitter(page, statement)

    # get description
    converter = AtCoderConverter(heading_style='ATX')
    description = converter.convert(statement.inner_html())
    description = re.sub(r'\n{3,}', '\n\n', description)

    return image, description

def fetch_problem_list() -> Iterator[tuple[str, Optional[str]]]:
    """
    Fetch problem list from AtCoder.

    Yields:
        tuple[str, Optional[str]]: A tuple of (problem_id, contest_id)
    """

    logger = logging.getLogger("Fetcher")
    resp = request_retry(10, lambda: requests.get(
        'https://kenkoooo.com/atcoder/resources/contest-problem.json',
        timeout=5,
    ), lambda retry_count, e: logger.exception(
        "Failed to fetch problem list from AtCoder: %s, retrying (%d)...",
        repr(e), retry_count
    ))
    if resp is None:
        logger.error("Failed to fetch problem list from AtCoder")
    else:
        for problem_info in resp.json():
            yield (problem_info['problem_id'], problem_info['contest_id'])
