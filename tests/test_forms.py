import pytest

from automation.forms import FormDetectionError, find_url_input
from tests.fakes import FakePage


def test_form_detector_finds_url_input():
    page = FakePage(selectors={'input[type="url"]': 1})

    assert find_url_input(page) == 'input[type="url"]'


def test_form_detector_finds_textarea():
    page = FakePage(selectors={"textarea": 1})

    assert find_url_input(page) == "textarea"


def test_form_detector_returns_clear_failure_when_no_input_exists():
    page = FakePage()

    with pytest.raises(FormDetectionError, match="No URL input field found"):
        find_url_input(page)
