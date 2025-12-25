import re

import bs4
from playwright.sync_api import Page
from PIL import Image
from markdownify import MarkdownConverter

from dataset.crawlers import (
    parent_convert, apply_visual_augmentations, get_screenshot_with_jitter
)


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
        return parent_convert(self, 'a', el, text, parent_tags)

    def convert_hN(self,
                   n: int,
                   el: bs4.element.Tag,
                   text: str,
                   parent_tags: set[str]) -> str:
        return super().convert_hN(n - 1, el, text, parent_tags)


def crawl_problem(page: Page, problem_id: str) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id from AtCoder

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in AtCoder.

    Returns:
        tuple[Image.Image, str]: A tuple of (image, description)
    """

    match = re.fullmatch(r'([a-zA-Z]+\d+)([a-zA-Z]+)', problem_id.lower())
    if match is None:
        raise RuntimeError("Invalid problem_id")
    contest, problem_index = match.groups()

    page.goto(f"https://atcoder.jp/contests/{contest}/tasks/{contest}_{problem_index}")
    page.wait_for_load_state("networkidle")

    # locate statement element
    statement = page.locator('#task-statement').locator('xpath=..')
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
