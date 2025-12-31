"""
Utils for text processing.
"""
import re
from typing import Optional, Literal, Iterable

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
