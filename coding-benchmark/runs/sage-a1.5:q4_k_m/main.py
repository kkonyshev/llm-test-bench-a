"""Task Tracker API — FastAPI + SQLite."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from fastapi.responses import Response


app = FastAPI()

DB_PATH = "tasks.db"
ALLOWED_PRIORITIES = ("low", "medium", "high")


def _ensure_tables(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()


@contextmanager
def _db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_tables(conn)
    try:
        yield conn
    finally:
        conn.close()


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None


class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: datetime


def to_dict(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


def task_from_row(row):
    if row is None:
        return None
    data = dict(row)
    data["completed"] = bool(data["completed"])
    return TaskRead(**data)


def get_task_by_id(conn, task_id):
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return task_from_row(row) if row is not None else None


def parse_completed(value):
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    raise HTTPException(status_code=422, detail="invalid value for 'completed'")


@app.on_event("startup")
def startup_event():
    with _db_conn() as conn:
        _ensure_tables(conn)


@app.post("/tasks", status_code=201)
async def create_task(body: TaskCreate):
    title = body.title
    if not title.strip():
        raise HTTPException(
            status_code=422, detail="title must not be empty after trimming"
        )
    priority = body.priority
    if priority is None:
        priority = "medium"
    elif priority not in ALLOWED_PRIORITIES:
        raise HTTPException(status_code=422, detail="invalid priority value")

    with _db_conn() as conn:
        created_at = datetime.now(timezone.utc)
        conn.execute(
            """INSERT INTO tasks (title, description, completed, priority, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (title, body.description, False, priority, created_at),
        )
        task_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return task_from_row(row)


@app.get("/tasks")
async def list_tasks(
    completed: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    with _db_conn() as conn:
        filters = []
        params = []
        if completed is not None:
            flag = parse_completed(completed)
            filters.append("completed = ?")
            params.append(1 if flag else 0)
        if priority is not None:
            if priority not in ALLOWED_PRIORITIES:
                raise HTTPException(status_code=422, detail="invalid priority value")
            filters.append("priority = ?")
            params.append(priority)

        where = "WHERE " + " AND ".join(filters) if filters else ""
        total = conn.execute(
            f"SELECT COUNT(*) FROM tasks {where}", tuple(params)
        ).fetchone()[0]

        query = f"SELECT * FROM tasks {where} ORDER BY id ASC LIMIT ? OFFSET ?"
        rows = conn.execute(
            query, tuple(params + [page_size, (page - 1) * page_size])
        ).fetchall()

    return {
        "items": [task_from_row(row) for row in rows],
        "total": int(total),
        "page": page,
        "page_size": page_size,
    }


@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    with _db_conn() as conn:
        task = get_task_by_id(conn, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/tasks/{task_id}")
async def update_task(task_id: int, body: TaskUpdate):
    with _db_conn() as conn:
        task = get_task_by_id(conn, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")

        data = to_dict(body)
        title = data.get("title")
        if title is not None:
            if not isinstance(title, str) or not title.strip() or len(title) > 200:
                raise HTTPException(status_code=422, detail="Invalid title")
        priority = data.get("priority")
        if priority is not None and priority not in ALLOWED_PRIORITIES:
            raise HTTPException(status_code=422, detail="Invalid priority value")

        updates = []
        values = []
        for field_name in ("title", "description", "completed", "priority"):
            if field_name in data:
                updates.append(f"{field_name} = ?")
                values.append(data[field_name])
        if updates:
            conn.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                tuple(values) + (task_id,),
            )

        return get_task_by_id(conn, task_id)


@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    with _db_conn() as conn:
        task = get_task_by_id(conn, task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
