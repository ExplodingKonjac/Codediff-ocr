import logging
import re
from itertools import count
from typing import Optional, Iterator

import bs4
import requests
from playwright.sync_api import Page
from PIL import Image
from markdownify import MarkdownConverter

from crawlers import (
    parent_convert, request_retry,
    apply_visual_augmentations, get_screenshot_with_jitter
)


class AcCodingConverter(MarkdownConverter):
    """Convert AcCoding statement to Markdown."""

    def convert_span(self,
                     el: bs4.element.Tag,
                     text: str,
                     parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if 'MathJax' in class_list:
            tex = el.next_sibling
            return "" if tex is None else f"${tex.text.strip()}$"
        return parent_convert(self, 'span', el, text, parent_tags)

    def convert_div(self,
                    el: bs4.element.Tag,
                    text: str,
                    parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if 'MathJax_Display' in class_list:
            tex = el.next_sibling
            return "" if tex is None else f"\n\n$$\n{tex.text.strip()}\n$$\n\n"
        return parent_convert(self, 'div', el, text, parent_tags)

    def convert_a(self,
                  el: bs4.element.Tag,
                  text: str,
                  parent_tags: set[str]) -> str:
        href = el.get('href')
        if text.replace('\\_', '_') == href:
            return f"<{href}>"
        return text

    def convert_img(self,
                    el: bs4.element.Tag,
                    text: str,
                    parent_tags: set[str]) -> str:
        return "[IMAGE]"


def crawl_problem(page: Page, *,
                  problem_id: str,
                  contest_id: Optional[str] = None) -> tuple[Image.Image, str]:
    """
    Crawl a problem of given problem_id from AcCoding.

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in AcCoding.
        contest_id (str): Not used, for compatibility with other crawlers.

    Returns:
        tuple[Image.Image, str]: A tuple of (image, description)
    """

    page.goto(f'https://accoding.buaa.edu.cn/problem/{problem_id}/index')
    page.wait_for_load_state('networkidle')

    statement = page.locator('.markdown-body')
    if not statement.is_visible():
        raise ValueError("Problem statement not found")

    # apply visual augmentations
    apply_visual_augmentations(page, statement)

    # take screenshot
    image = get_screenshot_with_jitter(page, statement)

    # get description
    converter = AcCodingConverter(heading_style='ATX')
    description = converter.convert(statement.inner_html())
    description = re.sub(r'\n{3,}', '\n\n', description)

    return image, description

def fetch_problem_list() -> Iterator[tuple[str, Optional[str]]]:
    """
    Fetch problem list from AcCoding.

    Yields:
        tuple[str, Optional[str]]: A tuple of (problem_id, contest_id)
    """

    logger = logging.getLogger("Fetcher")
    for page in count(0):
        resp = request_retry(5, lambda: requests.get(
            "https://accoding.buaa.edu.cn/problem/index",
            params={"page": page},
            timeout=5,
        ), lambda e, retry_count: logger.exception(
            "Failed to fetch problem list from AcCoding: %s, retrying (%d)...",
            repr(e), retry_count
        ))
        if resp is None:
            logger.error("Failed to fetch page %d of problem list from AcCoding", page)
        else:
            soup = bs4.BeautifulSoup(resp.text, 'html.parser')
            for tag in soup.find_all(id=re.compile(r'tr\d')):
                link = tag.find('a')
                if link is not None and link.text != '0':
                    href = link.get('href')
                    if isinstance(href, str):
                        yield (href.split('/')[0], None)
