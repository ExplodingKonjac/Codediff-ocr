import time

from playwright.sync_api import Page
from PIL import Image
from mistune import create_markdown
from mistune.plugins.math import math, math_in_list, math_in_quote
from mistune.plugins.formatting import strikethrough
from mistune.renderers.markdown import MarkdownRenderer

from dataset.crawlers.common import (
    apply_visual_augmentations, get_screenshot_with_jitter
)


class MyRenderer(MarkdownRenderer):
    """Override some methods to meet OCR need"""

    def image(self, token, state) -> str:
        return "[IMAGE]"

    def link(self, token, state) -> str:
        text = self.render_children(token, state)
        url = token['attrs']['url']
        return text if text != url else f"<{url}>"

    def thematic_break(self, token, state) -> str:
        return "---\n"

    def block_math(self, token, state) -> str:
        """Render block math"""
        return f"$$\n{token['raw']}\n$$\n\n"

    def inline_math(self, token, state) -> str:
        """Render block math"""
        return f"${token['raw']}$"


def crawl_problem(page: Page, problem_id: str) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id from Luogu

    Args:
        problem_id: The problem id to crawl
    
    Returns:
        A tuple of (image, description)
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
    time.sleep(0.2)
    description = page.evaluate('navigator.clipboard.readText()')

    markdown = create_markdown(
        renderer=MyRenderer(),
        plugins=[math, math_in_list, math_in_quote, strikethrough]
    )
    description = '\n'.join(description.split('\n')[2:])
    description = markdown(description)

    return image, description
