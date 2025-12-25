import time

from playwright.sync_api import Page
from PIL import Image
from mistune import create_markdown
from mistune.renderers.markdown import MarkdownRenderer

from dataset.crawlers import (
    apply_visual_augmentations, get_screenshot_with_jitter
)

def crawl_problem(page: Page, problem_id: str) -> tuple[Image.Image, str]:
    """
    Crawl problem statement of a given problem_id from Luogu

    Args:
        page (Page): The page object.
        problem_id (str): Problem ID in Luogu.
    
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
    time.sleep(0.2)
    description: str = page.evaluate('navigator.clipboard.readText()')

    description = description[description.index('\n\n') + 2:]
    return image, description
