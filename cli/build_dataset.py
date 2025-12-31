"""
Module including cli command build-dataset.
"""
import utils.rich_tqdmpatch

import os
import logging
from pathlib import Path

import click
from datasets import load_dataset, Dataset, DatasetDict, Image

from utils.rich_logging import RichLogManager

DEFAULT_WORKERS = max((os.cpu_count() or 1) - 2, 1)
SEED = 38567114

_log_manager = RichLogManager(level=logging.INFO)


class _IntOrFloatArg(click.ParamType):
    name = 'int_or_float'

    def convert(self, value, param, ctx):
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass
        raise click.BadParameter(f"{value} is not an int or float")


@click.command()
@click.option('--raw', '-r', 'raw', type=click.Path(exists=True, file_okay=False, path_type=Path), required=True)
@click.option('--output', '-o', 'output', type=click.Path(path_type=Path), required=True)
@click.option('--num-workers', '-j', 'num_workers', type=int, default=DEFAULT_WORKERS)
@click.option('--val-size', '-s', 'val_size', type=_IntOrFloatArg(), default="100")
@_log_manager.main_process
def build_dataset(raw: Path, output: Path, num_workers: int, val_size: float | int):
    """Build dataset from raw data."""

    logger = logging.getLogger('Main')
    logger.info("Building dataset from raw data path %s", raw)
    logger.info("Dataset output path set to %s", output)

    output.mkdir(parents=True, exist_ok=True)

    logger.info("Loading dataset from meta.jsonl...")
    ds = load_dataset(
        "json",
        data_files=str(raw / 'meta.jsonl'),
        split="train",
        num_proc=num_workers
    )

    logger.info("Dataset loaded, %d examples", len(ds))
    logger.info("Converting metadata...")
    ds = ds.map(
        lambda e: {'image': str(raw / e['image_path']), 'text': e['description']},
        remove_columns=['oj', 'problem_id', 'contest_id', 'image_path', 'description'],
        num_proc=num_workers
    )
    logger.info("Converting image path to Image...")
    ds = ds.cast_column("image", Image())
    logger.info("Filtering out images that are too large...")
    ds = ds.filter(lambda e: e['image'].size[0] * e['image'].size[1] < 2048 * 2048)
    assert isinstance(ds, Dataset)

    logger.info("Splitting dataset to TRAIN and VAL...")
    ds_split = ds.train_test_split(test_size=val_size, seed=SEED)
    assert isinstance(ds_split, DatasetDict)
    ds_split["val"] = ds_split.pop("test")
    logger.info(
        "Split done. TRAIN size: %d, VAL size: %d",
        len(ds_split["train"]), len(ds_split["val"])
    )

    logger.info("Saving dataset to %s...", output)
    ds_split.save_to_disk(output)

    logger.info("Done.")
