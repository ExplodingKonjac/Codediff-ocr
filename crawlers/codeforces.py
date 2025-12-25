import re

import bs4
from playwright.sync_api import Page
from PIL import Image
from markdownify import MarkdownConverter

from crawlers import (
    parent_convert, apply_visual_augmentations, get_screenshot_with_jitter
)


class CodeforcesConverter(MarkdownConverter):
    """Convert Codeforces statement to markdown"""

    def convert_div(self,
                    el: bs4.element.Tag,
                    text: str,
                    parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if 'title' in class_list:
            assert el.parent is not None
            parent_class_list = el.parent.get_attribute_list('class')
            if 'input' in parent_class_list or 'output' in parent_class_list:
                return f"\n\n### {text}\n\n"
            return f"\n\n# {text}\n\n"
        if 'section-title' in class_list:
            return f"\n\n## {text}\n\n"
        if 'input-output-copier' in class_list:
            return ""
        if 'time-limit' in class_list or \
           'memory-limit' in class_list or \
           'input-file' in class_list or \
           'output-file' in class_list:
            return parent_convert(self, 'div', el, el.get_text(': '), parent_tags)
        return parent_convert(self, 'div', el, text, parent_tags)

    def convert_span(self,
                     el: bs4.element.Tag,
                     text: str,
                     parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if 'MathJax' in class_list or 'MathJax_Display' in class_list:
            return ""
        return text

    def convert_script(self,
                       el: bs4.element.Tag,
                       text: str,
                       parent_tags: set[str]) -> str:
        if el.attrs.get('type') == 'math/tex':
            return f"${text}$"
        if el.attrs.get('type') == 'math/tex; mode=display':
            return f"\n\n$$\n{text}\n$$\n\n"
        return ""

    def convert_pre(self,
                    el: bs4.element.Tag,
                    text: str,
                    parent_tags: set[str]) -> str:
        text = el.get_text('\n')
        return parent_convert(self, 'pre', el, text, parent_tags)


def crawl_problem(page: Page, problem_id: str) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id from Codeforces

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in Codeforces.

    Returns:
        tuple[Image.Image, str]: A tuple of (image, description)
    """

    match = re.fullmatch(r'(\d+)([A-Z]+)', problem_id)
    if match is None:
        raise RuntimeError("invalid problem_id")

    contest_id, problem_index = match.groups()
    page.goto(f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}")
    page.wait_for_load_state("networkidle")

    # get statement element
    statement = page.locator('.problem-statement').first
    if not statement.is_visible():
        raise RuntimeError("Problem statement not found")

    # remove invisible elements
    statement.evaluate("""
    el => {
        el.querySelectorAll('*').forEach(el => {
            if (el.tagName.toLowerCase() === 'script') {
                return;
            }
            const style = window.getComputedStyle(el);
            if (style.display === 'none' ||
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
    converter = CodeforcesConverter(heading_style='ATX')
    description = converter.convert(statement.inner_html())

    return image, description
