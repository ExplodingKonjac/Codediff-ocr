from typing import Optional
from pathlib import Path

import click
from playwright.sync_api import sync_playwright
from PIL import Image

from crawlers import crawl_problem
from utils.text import format_markdown

@click.command()
@click.option('--state-file', 'state_file', type=str, default=None)
@click.option('--oj', 'oj', type=str, required=True)
@click.option('--problem-id', 'problem_id', type=str, required=True)
@click.option('--contest-id', 'contest_id', type=str, default=None)
def test_crawler(state_file: Optional[str],
                 oj: str,
                 problem_id: str,
                 contest_id: Optional[str]):
    """Test crawler"""

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel='msedge',
            headless=True
        )
        context = browser.new_context(
            storage_state=state_file,
            permissions=['clipboard-read', 'clipboard-write'],
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        image, description = crawl_problem(
            page,
            oj,
            problem_id=problem_id,
            contest_id=contest_id,
        )

        image: Image.Image = image.convert('RGB')
        description: str = format_markdown(description)

        image.save("output/image.png")
        Path('output/description.md').write_text(description, encoding='utf-8')
