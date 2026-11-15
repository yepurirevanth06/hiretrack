from typing import Any

from app.schemas.error import ErrorResponse

Responses = dict[int | str, dict[str, Any]]


def error(status_code: int, description: str) -> Responses:
    return {status_code: {"model": ErrorResponse, "description": description}}


AUTH_ERRORS: Responses = {
    **error(401, "Not authenticated"),
    **error(403, "Not allowed"),
}
