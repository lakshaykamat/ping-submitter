class FormDetectionError(Exception):
    pass


URL_INPUT_SELECTORS = (
    'input[type="url"]',
    'input[name*="url" i]',
    'input[name*="link" i]',
    'input[name*="site" i]',
    'input[name*="blog" i]',
    'input[name*="domain" i]',
    "textarea",
)

SUBMIT_SELECTORS = (
    'button[type="submit"]',
    'input[type="submit"]',
    'a:has-text("Send Pings")',
    'button:has-text("submit")',
    'button:has-text("ping")',
    'button:has-text("add")',
    'button:has-text("send")',
    'button:has-text("start")',
)


def find_url_input(page, adapter=None):
    if adapter and adapter.url_input_selector and selector_exists(page, adapter.url_input_selector):
        return adapter.url_input_selector

    for selector in URL_INPUT_SELECTORS:
        if selector_exists(page, selector):
            return selector

    raise FormDetectionError("No URL input field found.")


def find_submit_control(page, adapter=None):
    if adapter and adapter.submit_selector and selector_exists(page, adapter.submit_selector):
        return adapter.submit_selector

    for selector in SUBMIT_SELECTORS:
        if selector_exists(page, selector):
            return selector

    raise FormDetectionError("No submit control found.")


def fill_url_input(page, selector, submitted_url):
    page.locator(selector).first.fill(submitted_url)


def submit_form(page, selector):
    page.locator(selector).first.click()
    wait_for_page(page)


def selector_exists(page, selector):
    try:
        return page.locator(selector).count() > 0
    except Exception:
        return False


def wait_for_page(page):
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        return
