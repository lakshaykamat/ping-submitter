from automation.captcha import detect_captcha
from tests.fakes import FakePage


def test_captcha_detector_identifies_recaptcha_markup():
    page = FakePage(selectors={'iframe[src*="recaptcha"]': 1})

    assert detect_captcha(page) == 'iframe[src*="recaptcha"]'


def test_captcha_detector_identifies_image_captcha_markup():
    page = FakePage(selectors={'img[src*="captcha" i]': 1})

    assert detect_captcha(page) == 'img[src*="captcha" i]'
