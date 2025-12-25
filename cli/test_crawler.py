from tkinter.tix import Tree
from importlib import import_module
from pathlib import Path 

import click
from playwright.sync_api import sync_playwright

from dataset.crawlers import format_markdown

@click.command()
@click.option('--state-file', 'state_file', type=str, default=None)
@click.option('--oj', 'oj', type=str, required=True)
@click.option('--problem-id', 'problem_id', type=str, required=True)
def test_crawler(state_file: str | None, oj: str, problem_id: str):
    """Test crawler"""

    crawler = import_module(f'dataset.crawlers.{oj}')

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

        image, description = crawler.crawl_problem(page, problem_id)
        image.save("output/image.png")
        Path('output/description.md').write_text(
            format_markdown(description),
            encoding='utf-8'
        )
