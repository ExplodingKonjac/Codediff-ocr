import io
import re
import random
import time
from typing import Literal, Iterable, Optional, Callable, Iterator
from importlib import import_module

import bs4
import requests
from playwright.sync_api import Page, Locator
from PIL import Image
from pylatexenc.latexwalker import (
    LatexWalker, LatexNode, LatexCharsNode, LatexGroupNode, LatexCommentNode,
    LatexMacroNode, LatexEnvironmentNode, LatexMathNode, LatexSpecialsNode,
    get_default_latex_context_db
)
from pylatexenc.macrospec import std_macro, std_environment
from mistune import create_markdown
from mistune.plugins.math import math, math_in_list, math_in_quote
from mistune.plugins.formatting import strikethrough
from mistune.renderers.markdown import MarkdownRenderer


class _MyRenderer(MarkdownRenderer):
    """Override some methods to meet OCR need"""

    def image(self, token, state) -> str:
        return "[IMAGE]"

    def link(self, token, state) -> str:
        text = self.render_children(token, state)
        url = token['attrs']['url']
        return text if text != url else f"<{url}>"

    def thematic_break(self, token, state) -> str:
        return "---\n\n"

    def block_math(self, token, state) -> str:
        """Render block math"""
        return f"$$\n{format_latex(token['raw'])}\n$$\n\n"

    def inline_math(self, token, state) -> str:
        """Render block math"""
        return f"${format_latex(token['raw'])}$"


USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ' \
             'AppleWebKit/537.36 (KHTML, like Gecko) ' \
             'Chrome/143.0.0.0 ' \
             'Safari/537.36 ' \
             'Edg/143.0.0.0'

OJNames = Literal['accoding', 'atcoder', 'codeforces', 'loj', 'luogu']

_latex_ctx = get_default_latex_context_db()
_latex_ctx.add_context_category(
    'extra',
    macros=[
        std_macro('tfrac', False, 2),
        std_macro('dfrac', False, 2),
        std_macro('cfrac', False, 2),
        std_macro('binom', False, 2),
        std_macro('choose', False, 2),
        std_macro('boxed', False, 1)
    ],
    environments=[
        std_environment('aligned', None, is_math_mode=True),
        std_environment('gathered', None, is_math_mode=True),
    ]
)
_crawler_cache = {}

def request_retry(count: int,
                  req_func: Callable[[], requests.Response],
                  log_func: Callable[[int, Exception], None]) -> Optional[requests.Response]:
    """
    Retry a request with a given count.

    Args:
        count (int): The number of retries.
        req_func (Callable[[], requests.Response]): The function to call.
        log_func (Callable[[int], None]): The function to log.

    Returns:
        Optional[requests.Response]: The response if successful, None otherwise.
    """
    for _ in range(count):
        try:
            resp = req_func()
            resp.raise_for_status()
            return resp
        except Exception as e:
            log_func(_ + 1, e)
            time.sleep(1)
    return None

def parent_convert(obj: object,
                   tag_name: str,
                   el: bs4.element.Tag,
                   text: str,
                   parent_tags: set[str]) -> str:
    """Fallback to converter of parent"""

    f = getattr(super(type(obj), obj), f'convert_{tag_name}', None)
    return text if f is None else f(el, text, parent_tags)

def apply_visual_augmentations(page: Page, locator: Locator):
    """
    Apply visual augmentations to a page.

    Args:
        page (Page): The page to apply augmentations to.
        locator (Locator): The locator to apply augmentations to.
    """

    # resize viewport
    width = random.randint(1000, 2000)
    page.set_viewport_size({"width": width, "height": 1080})

    # inject css
    font_pool_en: dict[str, list[str]] = {
        'sans-serif': [
            'Arial', 'Segoe UI', 'Verdana', 'Tahoma', 'Microsoft Sans Serif',
            'DejaVu Sans', 'Liberation Sans', 'Ubuntu', 'FreeSans', 'Noto Sans',
        ],
        'serif': [
            'Times New Roman', 'Georgia', 'Palatino Linotype', 'DejaVu Serif',
            'Liberation Serif', 'FreeSerif', 'Noto Serif',
        ],
        'monospace': [
            'Courier New', 'Consolas', 'Lucida Console', 'DejaVu Sans Mono',
            'Liberation Mono', 'FreeMono', 'Noto Mono', 'Ubuntu Mono',
        ],
        'cursive': [
            'Comic Sans',
        ]
    }
    font_pool_zh: dict[str, list[str]] = {
        'sans-serif': [
            'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC',
        ],
        'serif': [
            'SimSun', 'NSimSun', 'Noto Serif CJK SC', 'AR PL UMing CN', 
        ],
        'monospace': [
            'Microsoft YaHei', 'Noto Sans CJK SC', 'SimSun',  'Noto Serif CJK SC',
        ],
        'cursive': [
            'KaiTi', 'FangSong', 'AR PL UKai CN',
        ]
    }

    category = random.choices(
        ['sans-serif', 'serif', 'monospace', 'cursive'],
        weights=[0.5, 0.3, 0.15, 0.05],
        k=1
    )[0]
    random.shuffle(font_pool_en[category])
    random.shuffle(font_pool_zh[category])

    font_family = ', '.join([
        *map(lambda s: "'" + s + "'", font_pool_en[category]),
        *map(lambda s: "'" + s + "'", font_pool_zh[category]),
        category
    ])
    font_size = random.choice(['12px', '14px', '16px', '18px'])
    line_height = random.choice(['1.0', '1.2', '1.5', '1.8'])

    locator.evaluate(f"""
    el => {{
        el.style.setProperty("font-family", "{font_family}", "important");
        el.style.setProperty("font-size", "{font_size}", "important");
        el.style.setProperty("line-height", "{line_height}", "important");
    }}
    """)

    # adjust height
    new_height = page.evaluate("document.body.scrollHeight")
    page.set_viewport_size({"width": width, "height": new_height})
    time.sleep(0.2)

def get_screenshot_with_jitter(page: Page, locator: Locator) -> Image.Image:
    """
    Get screenshot of a locator with a random jitter of borders.

    Args:
        page (Page): The page to take screenshot from.
        locator (Locator): The locator to take screenshot of.

    Returns:
        Image.Image: The screenshot of the locator.
    """
    rect = locator.bounding_box()
    if rect is None:
        raise RuntimeError("Failed to get bounding box")

    left = rect['x']
    top = rect['y']
    right = rect['x'] + rect['width']
    bottom = rect['y'] + rect['height']
    paddings = locator.evaluate("""
    el => {
        const style = window.getComputedStyle(el);
        return {
            top: parseInt(style.paddingTop),
            right: parseInt(style.paddingRight),
            bottom: parseInt(style.paddingBottom),
            left: parseInt(style.paddingLeft)
        }
    }
    """)

    max_extra = 50.0
    left += random.uniform(-max_extra, paddings['left'])
    top += random.uniform(-max_extra, paddings['top'])
    right += random.uniform(-paddings['right'], max_extra)
    bottom += random.uniform(-paddings['bottom'], max_extra)

    image_bytes = page.screenshot(clip={
        'x': left,
        'y': top,
        'width': right - left,
        'height': bottom - top
    })
    return Image.open(io.BytesIO(image_bytes))

def format_latex(tex: str, form: Literal['compact'] = 'compact') -> str:
    """
    Format latex code to a specific form.

    Args:
        tex (str): The latex code to format.
        form (Literal['compact']): The form to format the latex code to.

    Returns:
        str: The formatted latex code.
    """

    if form == 'compact':
        def format_node(node: LatexNode) -> str:
            result = ""
            if isinstance(node, LatexCharsNode):
                result = node.chars.strip()

            elif isinstance(node, LatexGroupNode):
                l, r = node.delimiters
                result = f'{l}{format_nodes(node.nodelist)}{r}'

            elif isinstance(node, LatexCommentNode):
                result = ''

            elif isinstance(node, LatexMacroNode):
                result = f'\\{node.macroname}'
                if node.nodeargd is not None:
                    result += format_args(node.nodeargd.argnlist)

            elif isinstance(node, LatexEnvironmentNode):
                result = f'\\begin{{{node.environmentname}}}' \
                         f'{format_args(node.nodeargd.argnlist)}' \
                         f' {format_nodes(node.nodelist)} ' \
                         f'\\end{{{node.environmentname}}}'

            elif isinstance(node, LatexMathNode):
                content = format_nodes(node.nodelist)
                if node.displaytype == 'display':
                    result = f'\n$$\n{content}\n$$\n'
                else:
                    result = f'${content}$'

            elif isinstance(node, LatexSpecialsNode):
                result = node.latex_verbatim()

            return result
    else:
        raise ValueError(f"Unknown form: {form}")

    def format_args(args: Optional[Iterable[LatexNode]]):
        result = ""
        if args is not None:
            for arg in args:
                s = format_node(arg)
                if isinstance(arg, LatexCharsNode):
                    s = f'{{{s}}}'
                result += s
        return result

    def format_nodes(nodes: Iterable[LatexNode]):
        return ' '.join(filter(lambda s: s != '', map(format_node, nodes)))

    walker = LatexWalker(tex, latex_context=_latex_ctx, tolerant_parsing=True)
    result = format_nodes(walker.get_latex_nodes()[0])

    # operators
    result = re.sub(r'([=\+\-<>/])', r' \1 ', result)
    # punctuations
    result = re.sub(r'\s*([,\.\:\;\!\?])\s*', r'\1 ', result)
    # remove spaces around ^ _
    result = re.sub(r'\s*([\^_])\s*', r'\1', result)
    # remove spaces before ) ] }
    result = re.sub(r'\s*([\)\]\}])', r'\1', result)
    # remove spaces after ( [ {
    result = re.sub(r'([\(\[\{])\s*', r'\1', result)
    # merge multiple spaces
    result = re.sub(r'\s+', ' ', result)

    return result.strip()

def format_markdown(markdown: str) -> str:
    """
    Format markdown to meet OCR need

    Args:
        markdown (str): The markdown to format

    Returns:
        str: The formatted markdown
    """

    md = create_markdown(
        renderer=_MyRenderer(),
        plugins=[math, math_in_list, math_in_quote, strikethrough]
    )
    result = md(markdown)
    assert isinstance(result, str)
    return result

def crawl_problem(page: Page,
                  oj: OJNames,
                  *,
                  problem_id: str,
                  contest_id: Optional[str] = None) -> tuple[Image.Image, str]:
    """
    Crawl a problem from a specific OJ.

    Args:
        oj (Literal['accoding', 'atcoder', 'codeforces', 'loj', 'luogu']): The OJ to crawl from.
        problem_id (str): The problem ID to crawl.
        contest_id (str): The contest ID to crawl.

    Returns:
        tuple[Image.Image, str]: The crawled problem image and description.
    """

    m = _crawler_cache.get(oj)
    if m is None:
        m = import_module(f"crawlers.{oj}")
        _crawler_cache[oj] = m
    return m.crawl_problem(page, problem_id=problem_id, contest_id=contest_id)

def fetch_problem_list(oj: OJNames) -> Iterator[tuple[str, Optional[str]]]:
    """
    Fetch problem list from a specific OJ.

    Args:
        oj (OJNames): The OJ to fetch from.

    Yields:
        tuple[str, Optional[str]]: A tuple of (problem_id, contest_id).
    """
    m = _crawler_cache.get(oj)
    if m is None:
        m = import_module(f"crawlers.{oj}")
        _crawler_cache[oj] = m
    return m.fetch_problem_list()
