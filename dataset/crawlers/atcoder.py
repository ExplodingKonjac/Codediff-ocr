import re

import bs4
import markdownify

from dataset.crawlers.common import (
	apply_visual_augmentations, get_screenshot_with_jitter
)

def crawl_problem(page: Page, problem_id: str) -> tuple[Image, str]:
