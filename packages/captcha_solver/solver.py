from packages.captcha_solver.client import OhMyCaptchaClient
from packages.captcha_solver.errors import CaptchaSolverError
from packages.captcha_solver.metadata import detect_captcha_metadata


class CaptchaSolver:
    def __init__(self, client=None):
        self.client = client or OhMyCaptchaClient()

    def solve_task(self, task):
        return self.client.solve_task(task)

    def solve_detected_captcha(self, page, adapter=None):
        metadata = detect_captcha_metadata(page, adapter=adapter)
        if metadata is None:
            raise CaptchaSolverError("No supported captcha with a site key was detected.")
        return self.solve_task(metadata.task)


def solve_detected_captcha(page, client=None, adapter=None):
    return CaptchaSolver(client=client).solve_detected_captcha(page, adapter=adapter)
