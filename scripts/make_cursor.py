import sys

from sqlalchemy import text

from app.core.pagination import encode_cursor
from app.db.session import engine

depth = int(sys.argv[1]) if len(sys.argv) > 1 else 90000

with engine.connect() as conn:
    row = conn.execute(
        text(
            "SELECT created_at, id FROM jobs WHERE status = 'open' "
            "ORDER BY created_at DESC, id DESC OFFSET :skip LIMIT 1"
        ),
        {"skip": depth - 1},
    ).one()

print(encode_cursor(row.created_at, row.id))
