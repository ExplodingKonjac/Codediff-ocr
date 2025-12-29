import click
from cli.save_cookies import save_cookies
from cli.test_crawler import test_crawler
from cli.build_dataset import build_dataset

@click.group()
def cli():
    pass

cli.add_command(save_cookies)
cli.add_command(test_crawler)
cli.add_command(build_dataset)
