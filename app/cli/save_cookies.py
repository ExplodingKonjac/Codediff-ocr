"""
Module including cli command save-cookies
"""
from pathlib import Path

import click
from playwright.sync_api import sync_playwright
from playwright.sync_api import Page

def _login_accoding(page: Page):
    click.echo("Logging into AcCoding...")
    page.goto('https://accoding.buaa.edu.cn/user/login')
    page.wait_for_load_state('networkidle')

    while True:
        email = click.prompt('Email')
        password = click.prompt('Password', hide_input=True)

        with page.expect_response(lambda resp: 'login' in resp.url) as response_info:
            page.locator('input[id="email"]').fill(email)
            page.locator('input[id="password"]').fill(password)
            page.locator('button[type="submit"]').click()
            page.wait_for_load_state('networkidle')

        if response_info.value.status == 302:
            click.echo("Login successful.")
            page.wait_for_url('https://accoding.buaa.edu.cn/index')
            break
        click.echo("Login failed. Try again.")

@click.command()
@click.option('--login-accoding', 'login_accoding', is_flag=True)
@click.option('--output', 'output', type=click.Path(path_type=Path), required=True)
def save_cookies(login_accoding: bool, output: Path):
    """Save cookies to file."""

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=False)
        context = browser.new_context()
        page = context.new_page()

        if login_accoding:
            _login_accoding(page)

        page.context.storage_state(path=output)
        click.echo(f"Storage state saved to {output}")
