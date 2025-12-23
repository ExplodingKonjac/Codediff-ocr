import io
import random
import time

from playwright.sync_api import Page, Locator
from PIL import Image

def apply_visual_augmentations(page: Page, locator: Locator):
    """
    Apply visual augmentations to a page

    Args:
        page: The page to apply augmentations to
        locator: The locator to apply augmentations to
        lang: The language of the page
    """

    # resize viewport
    width = random.randint(1000, 2000)
    page.set_viewport_size({"width": width, "height": 1080})
    print(f"[Augment] Changing width to {width}px")

    # inject css
    font_pool_en = {
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
    font_pool_zh = {
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
        *map(lambda s: f"'{s}'", font_pool_en[category]),
        *map(lambda s: f"'{s}'", font_pool_zh[category]),
        category
    ])
    font_size = random.choice(['14px', '16px', '18px', '20px'])
    line_height = random.choice(['1.0', '1.2', '1.5', '1.8'])

    locator.evaluate(f"""
    el => {{
        el.style.fontFamily = "{font_family}";
        el.style.fontSize = "{font_size}";
        el.style.lineHeight = "{line_height}";
    }}
    """)

    # adjust height
    new_height = page.evaluate("document.body.scrollHeight")
    page.set_viewport_size({"width": width, "height": new_height})

    print(
        f"[Augment] CSS injection: "
        f"fontFamily = {font_family}, "
        f"fontSize = {font_size}, "
        f"lineHeight = {line_height}"
    )
    time.sleep(0.2)

def get_screenshot_with_jitter(page: Page, locator: Locator) -> Image:
    """
    Get screenshot of a locator with a random jitter of borders

    Args:
        page: The page to take screenshot from
        locator: The locator to take screenshot of

    Returns:
        The screenshot of the locator
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
