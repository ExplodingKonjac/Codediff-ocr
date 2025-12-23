import time
import random
import io
from playwright.sync_api import Page
from PIL import Image

def _apply_visual_augmentations(page: Page):
    # resize viewport
    width = random.randint(1000, 1600)
    page.set_viewport_size({"width": width, "height": 2048})
    print(f"   [Augment] Changing width to {width}px")

    # inject css
    selected_font = random.choice([
        "Arial, sans-serif",
        "'Times New Roman', serif",
        "'Courier New', monospace",
        "'Microsoft YaHei', sans-serif",
        "Verdana, sans-serif",
        "Georgia, serif"
    ])
    font_size = random.choice(['14px', '16px', '18px', '20px'])
    line_height = random.choice(['1.2', '1.5', '1.8'])

    page.evaluate(f"""
        const target = document.querySelector('.problem') || document.body;
        target.style.fontFamily = "{selected_font}";
        target.style.fontSize = "{font_size}";
    """)
    print(
        f"   [Augment] CSS injection: "
        f"fontFamily = {selected_font.split(',')[0]}, "
        f"fontSize = {font_size}, "
        f"lineHeight = {line_height}"
    )

    time.sleep(0.2)

def _get_description(page: Page) -> str:
    copy_btn = page.locator('.problem-block-actions').get_by_text('Markdown').first
    if not copy_btn.is_visible():
        raise RuntimeError("Copy button not found")

    copy_btn.click()
    time.sleep(0.5)
    description = page.evaluate('navigator.clipboard.readText()')

    # strip first two lines - problem title
    description = '\n'.join(description.split('\n')[2:])
    return description

def _get_screenshot(page: Page) -> Image:
    locator = page.locator('.problem').first
    if not locator.is_visible():
        raise RuntimeError("Problem content not found")

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

def crawl_problem(page: Page, problem_id: str) -> tuple[Image, str]:
    """
    Crawl problem statement of a given problem_id from Luogu

    Args:
        problem_id: The problem id to crawl
    
    Returns:
        A tuple of (image, description)
    """

    page.goto(f'https://www.luogu.com.cn/problem/{problem_id}')
    page.wait_for_load_state('networkidle')

    _apply_visual_augmentations(page)
    description = _get_description(page)
    image = _get_screenshot(page)
    return image, description
