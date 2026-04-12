from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator

from .db import Database
from .utils import utc_now_iso


@contextmanager
def tracked_job(db: Database, job_name: str) -> Iterator[Dict[str, Any]]:
    started_at = utc_now_iso()
    job_run_id = db.start_job_run(job_name, started_at)
    db.commit()
    state: Dict[str, Any] = {"job_run_id": job_run_id, "started_at": started_at, "rows_written": None, "meta": {}}
    try:
        yield state
    except Exception as exc:
        db.rollback()
        db.finish_job_run(
            job_run_id,
            finished_at=utc_now_iso(),
            status="failed",
            rows_written=state.get("rows_written"),
            meta=state.get("meta"),
            error_text=str(exc),
        )
        db.commit()
        raise
    else:
        db.finish_job_run(
            job_run_id,
            finished_at=utc_now_iso(),
            status="completed",
            rows_written=state.get("rows_written"),
            meta=state.get("meta"),
        )
        db.commit()
