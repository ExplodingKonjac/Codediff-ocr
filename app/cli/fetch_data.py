"""
Module including cli command fetch-data.
"""
import logging
import uuid
import os
import json
import time
from dataclasses import dataclass, asdict
from multiprocessing import Queue, Process
from typing import Optional, Literal
from pathlib import Path

import click
from playwright.sync_api import sync_playwright, Page
from rich.progress import (
    Progress, TextColumn, BarColumn, TimeRemainingColumn, TimeElapsedColumn,
    MofNCompleteColumn
)
from PIL import Image

from app.crawlers import crawl_problem, fetch_problem_list
from app.utils.rich_logging import RichLogManager
from app.utils.web import USER_AGENT
from app.utils.text import format_markdown

RESTART_LOOPS = 100
DEFAULT_WORKERS = max((os.cpu_count() or 1) - 2, 1)

_log_manager = RichLogManager(level=logging.INFO)


@dataclass(frozen=True)
class Problem:
    """Stores information about a problem."""
    oj: Literal['accoding', 'atcoder', 'codeforces', 'loj', 'luogu']
    problem_id: str
    contest_id: Optional[str]


@_log_manager.sub_process
def _producer_process(output_path: Path,
                      num_workers: int,
                      task_queue: Queue,
                      report_queue: Queue):
    logger = logging.getLogger("Fetcher")

    tasks_done: set[Problem] = set()
    try:
        with open(output_path / 'meta.jsonl', 'r', encoding='utf-8') as f:
            for line in f.readlines():
                record = json.loads(line)
                tasks_done.add(Problem(
                    oj=record['oj'],
                    contest_id=record['contest_id'],
                    problem_id=record['problem_id'],
                ))
    except FileNotFoundError:
        (output_path / 'meta.jsonl').touch()
    except Exception:
        logger.exception("Error reading meta.jsonl")

    task_count = 0
    for oj in ('atcoder', 'codeforces', 'loj', 'luogu', 'accoding'):
    # for oj in ('luogu',):
        logger.info("Fetching problem list from %s...", oj)
        for problem_id, contest_id in fetch_problem_list(oj):
            task = Problem(oj=oj, problem_id=problem_id, contest_id=contest_id)
            logger.info("get task %s", task.problem_id)
            if task not in tasks_done:
                task_queue.put(task)
                report_queue.put(1)
                task_count += 1

    for _ in range(num_workers):
        task_queue.put(None)
    logger.info("Fetching done. %d tasks in total.", task_count)

@_log_manager.sub_process
def _worker_process(worker_id: int,
                    state_file: Optional[Path],
                    output_path: Path,
                    task_queue: Queue,
                    report_queue: Queue):
    logger = logging.getLogger(f'Worker-{worker_id}')
    logger.info("Launched.")

    output_path = Path(output_path) / 'images'
    output_path.mkdir(parents=True, exist_ok=True)
    if state_file is not None:
        state_file = Path(state_file)

    def _process_one(page: Page, problem: Problem):
        image, description = crawl_problem(
            page,
            problem.oj,
            problem_id=problem.problem_id,
            contest_id=problem.contest_id
        )

        image = image.convert('RGB').quantize(
            colors=256,
            method=Image.Quantize.FASTOCTREE,
            dither=Image.Dither.NONE,
        )
        description = format_markdown(description)

        image_path = output_path / (uuid.uuid1().hex + '.png')
        image.save(image_path, format='png')
        report_queue.put((problem, f'images/{image_path.name}', description))

        logger.info("Problem done: %s", json.dumps(asdict(problem)))

    while True:
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(
                    channel='msedge',
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-infobars",
                    ],
                )
                context = browser.new_context(
                    storage_state=state_file,
                    user_agent=USER_AGENT,
                    permissions=['clipboard-read', 'clipboard-write'],
                )
                page = context.new_page()
            except Exception:
                logger.exception("Error launching browser")
                continue

            for _ in range(RESTART_LOOPS):
                try:
                    problem = task_queue.get()
                    if problem is None:
                        logger.info("exiting...")
                        report_queue.put(None)
                        logger.info("Finished.")
                        return
                except Exception:
                    logger.info("Error when getting task, retry after 1 second...")
                    time.sleep(1)
                    continue
                try:
                    _process_one(page, problem)
                except Exception:
                    logger.exception("Error processing problem %s", asdict(problem))

            logger.info("Reached restart limit, restarting browser...")


@click.command()
@click.option('--output', '-o', 'output_path', type=click.Path(path_type=Path), required=True)
@click.option('--num-workers', '-j', 'num_workers', type=int, default=DEFAULT_WORKERS)
@click.option('--state-file', 'state_file', type=click.Path(path_type=Path), default=None)
@_log_manager.main_process
def fetch_data(output_path: Path, num_workers: int, state_file: Optional[str]):
    """Fetch the data from OJs."""

    logger = logging.getLogger("Main")
    logger.info("Output path set to %s", output_path)
    logger.info("Using %d workers.", num_workers)
    if state_file is not None:
        logger.info("Using storage_state from %s.", state_file)

    output_path.mkdir(parents=True, exist_ok=True)

    task_queue = Queue()
    report_queue = Queue()
    processes: list[Process] = []

    processes.append(Process(
        target=_producer_process,
        args=(output_path, num_workers, task_queue, report_queue)
    ))
    for i in range(num_workers):
        processes.append(Process(
            target=_worker_process,
            args=(i, state_file, output_path, task_queue, report_queue)
        ))
    for process in processes:
        process.start()

    with (
        Progress(
            TextColumn("[progress.description]{task.description}"),
            TextColumn("[progress.percentage]{task.percentage:>5.1f}%"),
            BarColumn(bar_width=None),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=True,
            expand=True,
        ) as progress,
        open(Path(output_path) / 'meta.jsonl', 'a', encoding='utf-8') as f,
    ):
        task_id = progress.add_task("Processing problems...", total=None)

        finished_count = 0
        while finished_count < num_workers:
            result = report_queue.get()
            if result is None:
                finished_count += 1
            elif isinstance(result, int):
                old_total = progress.tasks[task_id].total or 0
                progress.update(task_id, total=old_total + result)
            else:
                task, image_path, description = result
                record = {
                    'oj': task.oj,
                    'contest_id': task.contest_id,
                    'problem_id': task.problem_id,
                    'image_path': str(image_path),
                    'description': description
                }
                f.write(json.dumps(record) + '\n')
                progress.advance(task_id, 1)

    for process in processes:
        process.join()
    logger.info("Done.")
