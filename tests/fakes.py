class FakeResponse:
    def __init__(self, status=200):
        self.status = status


class FakeLocator:
    def __init__(self, page, selector):
        self.page = page
        self.selector = selector

    @property
    def first(self):
        return self

    def count(self):
        return self.page.selectors.get(self.selector, 0)

    def fill(self, value):
        self.page.filled[self.selector] = value

    def click(self):
        self.page.clicked.append(self.selector)

    def check(self):
        self.page.checked.append(self.selector)


class FakePage:
    def __init__(self, selectors=None, html="", goto_errors=None, response_status=200):
        self.selectors = selectors or {}
        self.html = html
        self.goto_errors = list(goto_errors or [])
        self.response_status = response_status
        self.goto_count = 0
        self.filled = {}
        self.clicked = []
        self.checked = []
        self.screenshots = []

    def locator(self, selector):
        return FakeLocator(self, selector)

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_count += 1
        if self.goto_errors:
            raise self.goto_errors.pop(0)
        return FakeResponse(self.response_status)

    def content(self):
        return self.html

    def wait_for_load_state(self, state, timeout=None):
        return None

    def screenshot(self, path, full_page=True):
        self.screenshots.append(path)
        with open(path, "wb") as screenshot_file:
            screenshot_file.write(b"fake screenshot")


class FakeBrowserManager:
    def __init__(self, pages):
        self.pages = list(pages)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def new_page(self):
        if not self.pages:
            raise AssertionError("No fake pages left.")
        return self.pages.pop(0)


class TemporaryNetworkError(Exception):
    pass
