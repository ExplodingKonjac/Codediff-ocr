from playwright.sync_api import sync_playwright
from dataset.crawlers.loj import crawl_problem

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="msedge",
            headless=False
        )
        context = browser.new_context(
            permissions=['clipboard-read', 'clipboard-write'],
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()

        image, description = crawl_problem(page, "552")
        image.save("output/image.png")
        print(description)
