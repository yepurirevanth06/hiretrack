import base64
import json
from datetime import datetime

from app.core.exceptions import InvalidCursorError


def encode_cursor(created_at: datetime, row_id: int) -> str:
    payload = json.dumps({"created_at": created_at.isoformat(), "id": row_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return datetime.fromisoformat(payload["created_at"]), int(payload["id"])
    except (ValueError, KeyError, TypeError) as exc:
        raise InvalidCursorError("Invalid cursor") from exc
