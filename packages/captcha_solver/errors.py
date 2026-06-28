class CaptchaSolverError(Exception):
    pass


class CaptchaSolverApiError(CaptchaSolverError):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response or {}


class CaptchaSolverTimeoutError(CaptchaSolverError):
    pass
