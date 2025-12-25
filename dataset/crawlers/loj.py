import bs4
from playwright.sync_api import Page
from PIL import Image
from markdownify import MarkdownConverter

from dataset.crawlers import (
    parent_convert, apply_visual_augmentations, get_screenshot_with_jitter
)


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
        return parent_convert(self, 'div', el, text, parent_tags)

    def convert_a(self,
                  el: bs4.element.Tag,
                  text: str,
                  parent_tags: set[str]) -> str:
        class_list = el.get_attribute_list('class')
        if '_copySample_1rcs8_202' in class_list:
            return ""
        return parent_convert(self, 'a', el, text, parent_tags)


def crawl_problem(page: Page, problem_id: str) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id in LOJ

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in LOJ.

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
