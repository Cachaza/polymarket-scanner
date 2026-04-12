from __future__ import annotations

import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def read_connection(database_url: str) -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(database_url, row_factory=dict_row)
    conn.autocommit = True  # read-only queries; no need for transactions
    try:
        yield conn
    finally:
        conn.close()
