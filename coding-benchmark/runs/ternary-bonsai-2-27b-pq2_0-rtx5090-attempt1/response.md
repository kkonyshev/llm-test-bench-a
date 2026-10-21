```python
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel

DB_PATH = Path("tasks.db")
ALLOWED_PRIORITIES = ("low", "medium", "high")


class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str


class TaskListOut(BaseModel):
    items: List[TaskOut]
    total: int
    page: int
    page_size: int


def _get_db():
    return sqlite3.connect(DB_PATH, row_factory=sqlite3.Row)


def _init_db() -> None:
    conn = _get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.close()


def _validate_title(title: str) -> str:
    if not isinstance(title, str):
        raise HTTPException(status_code=422, detail="title must be a string")
    if len(title) > 200 or not title.strip():
        raise HTTPException(
            status_code=422,
            detail="title must be 1-200 chars and non-empty after trim",
        )
    return title


def _validate_priority(priority: str) -> str:
    if not isinstance(priority, str) or priority not in ALLOWED_PRIORITIES:
        raise HTTPException(
            status_code=422,
            detail="priority must be one of low, medium, high",
        )
    return priority


def _task_from_row(row: sqlite3.Row) -> TaskOut:
    return TaskOut(
        id=int(row["id"]),
        title=str(row["title"]),
        description=row["description"],
        completed=bool(row["completed"]),
        priority=str(row["priority"]),
        created_at=str(row["created_at"]),
    )


def _filter_clause(completed: Optional[bool], priority: Optional[str]):
    clauses: List[str] = []
    params: List[object] = []

    if completed is not None:
        clauses.append("completed = ?")
        params.append(1 if completed else 0)

    if priority is not None:
        clauses.append("priority = ?")
        params.append(priority)

    where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where_sql, params


def _select_task_row(conn: sqlite3.Connection, task_id: int):
    row = conn.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    return row


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_init_db()
app = FastAPI(title="Task Tracker API")


@app.post("/tasks", status_code=201, response_model=TaskOut)
def create_task(body: dict = Body(...)):
    if body is None:
        body = {}

    title = _validate_title(body.get("title"))

    description: Optional[str] = None
    if "description" in body:
        value = body["description"]
        if value is not None and not isinstance(value, str):
            raise HTTPException(status_code=422, detail="description must be a string or null")
        description = value

    priority = "medium"
    if "priority" in body:
        priority = _validate_priority(body["priority"])

    created_at = _now_iso()

    conn = _get_db()
    try:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, completed, priority, created_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (title, description, priority, created_at),
        )
        conn.commit()
        row = _select_task_row(conn, cur.lastrowid)
        if row is None:
            raise HTTPException(status_code=500, detail="failed to load created task")
        return _task_from_row(row)
    finally:
        conn.close()


@app.get("/tasks", response_model=TaskListOut)
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(10),
):
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=422, detail="page_size must be 1-100 inclusive")
    if priority is not None:
        _validate_priority(priority)

    where_sql, params = _filter_clause(completed, priority)
    offset = (page - 1) * page_size

    conn = _get_db()
    try:
        count_row = conn.execute(f"SELECT COUNT(*) FROM tasks{where_sql}", params).fetchone()
        rows = conn.execute(
            f"""
            SELECT id, title, description, completed, priority, created_at
            FROM tasks{where_sql}
            ORDER BY id ASC
            LIMIT ? OFFSET ?
            """,
            params + [offset, page_size],
        ).fetchall()

        return TaskListOut(
            items=[_task_from_row(row) for row in rows],
            total=int(count_row[0]),
            page=page,
            page_size=page_size,
        )
    finally:
        conn.close()


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    conn = _get_db()
    try:
        row = _select_task_row(conn, task_id)
        if row is None:
            raise HTTPException(status_code=404, detail="task not found")
        return _task_from_row(row)
    finally:
        conn.close()


@app.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: dict = Body(None)):
    if body is None:
        body = {}

    if not isinstance(body, dict):
        raise HTTPException(status_code=422, detail="body must be a JSON object")

    fields: dict = {}

    for key, value in body.items():
        if key == "title":
            fields["title"] = _validate_title(value)
        elif key == "description":
            if value is not None and not isinstance(value, str):
                raise HTTPException(status_code=422, detail="description must be a string or null")
            fields["description"] = value
        elif key == "completed":
            if type(value) is not bool:
                raise HTTPException(status_code=422, detail="completed must be boolean")
            fields["completed"] = value
        elif key == "priority":
            fields["priority"] = _validate_priority(value)

    conn = _get_db()
    try:
        row = _select_task_row(conn, task_id)
        if row is None:
            raise HTTPException(status_code=404, detail="task not found")

        if fields:
            clauses: List[str] = []
            params: List[object] = []

            if "title" in fields:
                clauses.append("title = ?")
                params.append(fields["title"])

            if "description" in fields:
                clauses.append("description = ?")
                params.append(fields["description"])

            if "completed" in fields:
                clauses.append("completed = ?")
                params.append(1 if fields["completed"] else 0)

            if "priority" in fields:
                clauses.append("priority = ?")
                params.append(fields["priority"])

            conn.execute(
                f"UPDATE tasks SET {', '.join(clauses)} WHERE id = ?",
                params + [task_id],
            )
            conn.commit()
            row = _select_task_row(conn, task_id)
            if row is None:
                raise HTTPException(status_code=404, detail="task not found")

        return _task_from_row(row)
    finally:
        conn.close()


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = _get_db()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="task not found")
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
```