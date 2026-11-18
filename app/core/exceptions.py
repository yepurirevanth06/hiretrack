class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ServiceUnavailableError(AppError):
    status_code = 503
    code = "service_unavailable"


class InvalidTransitionError(AppError):
    status_code = 409
    code = "invalid_transition"


class InvalidCursorError(AppError):
    status_code = 400
    code = "invalid_cursor"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class UnprocessableError(AppError):
    status_code = 422
    code = "unprocessable"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"


class AIUnavailableError(AppError):
    """The AI provider couldn't be reached, timed out, or isn't configured."""

    status_code = 503
    code = "ai_unavailable"


class AIOutputError(AppError):
    """The AI provider answered, but not with something we can use."""

    status_code = 502
    code = "ai_bad_output"
