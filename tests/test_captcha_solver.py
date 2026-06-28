from dataclasses import dataclass

from packages.captcha_solver import detect_captcha, fill_captcha_answer


class FakeLocator:
    def __init__(self, count):
        self._count = count
        self.filled_values = []
        self.first = self

    def count(self):
        return self._count

    def fill(self, value):
        self.filled_values.append(value)


class FakePage:
    def __init__(self, selector_counts):
        self.locators = {
            selector: FakeLocator(count)
            for selector, count in selector_counts.items()
        }

    def locator(self, selector):
        return self.locators.get(selector, FakeLocator(0))


@dataclass
class FakeAdapter:
    captcha_selectors: tuple[str, ...]


def test_detect_captcha_returns_first_matching_selector():
    page = FakePage({".h-captcha": 1})

    assert detect_captcha(page) == ".h-captcha"


def test_detect_captcha_includes_adapter_selectors():
    page = FakePage({"#custom-captcha": 1})
    adapter = FakeAdapter(captcha_selectors=("#custom-captcha",))

    assert detect_captcha(page, adapter=adapter) == "#custom-captcha"


def test_fill_captcha_answer_uses_first_answer_selector():
    selector = 'input[name*="captcha" i]'
    page = FakePage({selector: 1})

    assert fill_captcha_answer(page, "42") is True
    assert page.locators[selector].filled_values == ["42"]
