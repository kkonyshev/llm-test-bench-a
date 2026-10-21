import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel

DB_PATH = "tasks.db"
ALLOWED_PRIORITIES = {"low", "medium", "high"}
DEFAULT_PRIORITY = "medium"


def _init_db():
    conn = sqlite3.connect(DB_PATH)
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
    conn.commit()
    conn.close()


_init_db()

app = FastAPI()


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


class TaskListResponse(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int


def _clean_title(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned or len(cleaned) > 200:
        return None
    return cleaned


def _valid_priority(value):
    return isinstance(value, str) and value in ALLOWED_PRIORITIES


def _invalid(detail):
    raise HTTPException(status_code=422, detail=detail)


def _task_from_row(row):
    return Task(
        id=row[0],
        title=row[1],
        description=row[2],
        completed=bool(row[3]),
        priority=row[4],
        created_at=row[5],
    )


def _get_task(task_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return row


@app.post("/tasks", status_code=201, response_model=Task)
def create_task(payload: Optional[dict] = Body(None)):
    if payload is None:
        payload = {}

    if "title" not in payload or payload["title"] is None:
        _invalid("title is required and must be a non-empty string")

    title = _clean_title(payload["title"])
    if title is None:
        _invalid("title must be a string of 1 to 200 characters after trimming")

    description = None
    if "description" in payload:
        description = payload["description"]
        if description is not None and not isinstance(description, str):
            _invalid("description must be a string or null")

    priority = DEFAULT_PRIORITY
    if "priority" in payload:
        value = payload["priority"]
        if value is None:
            priority = DEFAULT_PRIORITY
        elif not _valid_priority(value):
            _invalid("priority must be one of low, medium, high")
        else:
            priority = value

    created_at = datetime.now(timezone.utc).iso()

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            "INSERT INTO tasks (title, description, completed, priority, created_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (title, description, priority, created_at),
        )
        task_id = cur.lastrowid

    return Task(
        id=task_id,
        title=title,
        description=description,
        completed=False,
        priority=priority,
        created_at=created_at,
    )


@app.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1),
    page_size: int = Query(10),
):
    if page < 1:
        _invalid("page must be >= 1")
    if page_size < 1 or page_size > 100:
        _invalid("page_size must be between 1 and 100")
    if priority is not None and not _valid_priority(priority):
        _invalid("priority must be one of low, medium, high")

    count_query = "SELECT COUNT(*) FROM tasks WHERE 1 = 1"
    count_params = []

    if completed is not None:
        count_query += " AND completed = ?"
        count_params.append(1 if completed else 0)

    if priority is not None:
        count_query += " AND priority = ?"
        count_params.append(priority)

    with sqlite3.connect(DB_PATH) as conn:
        total = conn.execute(count_query, count_params).fetchone()[0]

    offset = (page - 1) * page_size
    limit = page_size

    items_query = (
        "SELECT id, title, description, completed, priority, created_at "
        "FROM tasks WHERE 1 = 1 ORDER BY id ASC LIMIT ? OFFSET ?"
    )
    query_params = []

    if completed is not None:
        items_query += " AND completed = ?"
        query_params.append(1 if completed else 0)

    if priority is not None:
        items_query += " AND priority = ?"
        query_params.append(priority)

    query_params.extend([limit, offset])

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(items_query, query_params).fetchall()

    return TaskListResponse(
        items=[_task_from_row(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    row = _get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_from_row(row)


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, payload: Optional[dict] = Body(None)):
    if payload is None:
        payload = {}

    updates = {}

    if "title" in payload and payload["title"] is not None:
        title = _clean_title(payload["title"])
        if title is None:
            _invalid("title must be a string of 1 to 200 characters after trimming")
        updates["title"] = title

    if "description" in payload:
        description = payload["description"]
        if description is not None and not isinstance(description, str):
            _invalid("description must be a string or null")
        updates["description"] = description

    if "completed" in payload and payload["completed"] is not None:
        completed = payload["completed"]
        if not isinstance(completed, bool):
            _invalid("completed must be a boolean")
        updates["completed"] = completed

    if "priority" in payload and payload["priority"] is not None:
        priority = payload["priority"]
        if not _valid_priority(priority):
            _invalid("priority must be one of low, medium, high")
        updates["priority"] = priority

    row = _get_task(task_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if updates:
        set_clauses = []
        values = []

        if "title" in updates:
            set_clauses.append("title = ?")
            values.append(updates["title"])

        if "description" in updates:
            set_clauses.append("description = ?")
            values.append(updates["description"])

        if "completed" in updates:
            set_clauses.append("completed = ?")
            values.append(1 if updates["completed"] else 0)

        if "priority" in updates:
            set_clauses.append("priority = ?")
            values.append(updates["priority"])

        values.append(task_id)

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?",
                values,
            )

    row = _get_task(task_id)
    return _task_from_row(row)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
