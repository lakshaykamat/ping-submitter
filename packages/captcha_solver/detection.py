CAPTCHA_SELECTORS = (
    'iframe[src*="recaptcha"]',
    ".g-recaptcha",
    'iframe[src*="hcaptcha"]',
    ".h-captcha",
    'iframe[src*="challenges.cloudflare.com"]',
    '[id*="captcha" i]',
    '[class*="captcha" i]',
    '[name*="captcha" i]',
    'img[src*="captcha" i]',
)

CAPTCHA_ANSWER_SELECTORS = (
    'input[name*="captcha" i]',
    'input[id*="captcha" i]',
    'textarea[name*="captcha" i]',
)


def detect_captcha(page, adapter=None):
    selectors = list(CAPTCHA_SELECTORS)
    if adapter:
        selectors.extend(adapter.captcha_selectors)

    for selector in selectors:
        if selector_exists(page, selector):
            return selector
    return None


def fill_captcha_answer(page, answer):
    for selector in CAPTCHA_ANSWER_SELECTORS:
        if selector_exists(page, selector):
            page.locator(selector).first.fill(answer)
            return True
    return False


def selector_exists(page, selector):
    try:
        return page.locator(selector).count() > 0
    except Exception:
        return False
