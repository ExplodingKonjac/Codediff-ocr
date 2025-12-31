import click
from app.cli.save_cookies import save_cookies
from app.cli.test_crawler import test_crawler
from app.cli.fetch_data import fetch_data
from app.cli.build_dataset import build_dataset
from app.cli.train import train

@click.group()
def cli():
    pass

cli.add_command(save_cookies)
cli.add_command(test_crawler)
cli.add_command(fetch_data)
cli.add_command(build_dataset)
cli.add_command(train)
