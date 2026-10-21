```python
from datetime import datetime, timezone
import sqlite3
from enum import Enum
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel

try:
    from pydantic import field_validator

    _PYDANTIC_V2 = True
except ImportError:
    from pydantic import validator

    _PYDANTIC_V2 = False

DB_PATH = "tasks.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    priority TEXT NOT NULL DEFAULT 'medium',
    created_at TEXT NOT NULL
)
"""


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


def _pydantic_validate_title(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("title must be a string")

    title = value.strip()
    if len(title) < 1 or len(title) > 200:
        raise ValueError("title must be 1-200 characters")

    return title


def _http_validate_title(value: object) -> str:
    try:
        return _pydantic_validate_title(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def _priority_to_db(value) -> str:
    if isinstance(value, Priority):
        return value.value
    return str(value)


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_unset=True)
    return model.dict(exclude_unset=True)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(_SCHEMA_SQL)
        conn.commit()
    except Exception:
        conn.close()
        raise

    conn.row_factory = sqlite3.Row
    return conn


def _row_to_task(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "completed": bool(row["completed"]),
        "priority": row["priority"],
        "created_at": row["created_at"],
    }


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: Priority
    created_at: datetime


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Priority = Priority.medium

    if _PYDANTIC_V2:
        @field_validator("title")
        @classmethod
        def _validate_title(cls, v: str) -> str:
            return _pydantic_validate_title(v)
    else:
        @validator("title")
        def _validate_title(cls, v: str) -> str:
            return _pydantic_validate_title(v)


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Priority] = None

    if _PYDANTIC_V2:
        @field_validator("title")
        @classmethod
        def _validate_title(cls, v: Optional[str]) -> str:
            if v is None:
                raise ValueError("title must not be null")
            return _pydantic_validate_title(v)

        @field_validator("completed")
        @classmethod
        def _validate_completed(cls, v: Optional[bool]) -> bool:
            if v is None:
                raise ValueError("completed must not be null")
            return v

        @field_validator("priority")
        @classmethod
        def _validate_priority(cls, v: Optional[Priority]) -> Priority:
            if v is None:
                raise ValueError("priority must not be null")
            return v
    else:
        @validator("title")
        def _validate_title(cls, v: Optional[str]) -> str:
            if v is None:
                raise ValueError("title must not be null")
            return _pydantic_validate_title(v)

        @validator("completed")
        def _validate_completed(cls, v: Optional[bool]) -> bool:
            if v is None:
                raise ValueError("completed must not be null")
            return v

        @validator("priority")
        def _validate_priority(cls, v: Optional[Priority]) -> Priority:
            if v is None:
                raise ValueError("priority must not be null")
            return v


class TaskListResponse(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int


app = FastAPI(title="Task Tracker API")


@app.on_event("startup")
def startup():
    init_db()


@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: TaskCreate):
    created_at = datetime.now(timezone.utc).isoformat()

    conn = _get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO tasks (title, description, completed, priority, created_at)
            VALUES (?, ?, 0, ?, ?)
            """,
            (
                task.title,
                task.description,
                _priority_to_db(task.priority),
                created_at,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()
    finally:
        conn.close()

    return _row_to_task(row)


@app.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    completed: Optional[bool] = Query(default=None),
    priority: Optional[Priority] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    conditions = []
    params = []

    if completed is not None:
        conditions.append("completed = ?")
        params.append(1 if completed else 0)

    if priority is not None:
        conditions.append("priority = ?")
        params.append(_priority_to_db(priority))

    where_clause = ""
    if conditions:
        where_clause = " WHERE " + " AND ".join(conditions)

    offset = (page - 1) * page_size

    conn = _get_connection()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM tasks{where_clause}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM tasks{where_clause} ORDER BY id ASC LIMIT ? OFFSET ?",
            params + [page_size, offset],
        ).fetchall()
    finally:
        conn.close()

    return {
        "items": [_row_to_task(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        return _row_to_task(row)
    finally:
        conn.close()


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task_update: TaskUpdate):
    data = _model_dump(task_update)

    # Fallback guard; normally handled by model validators.
    for field in ("title", "completed", "priority"):
        if field in data and data[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} must not be null")

    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")

        title = row["title"]
        description = row["description"]
        completed = bool(row["completed"])
        priority = row["priority"]

        if "title" in data:
            title = _http_validate_title(data["title"])

        if "description" in data:
            description = data["description"]
            if description is not None and not isinstance(description, str):
                raise HTTPException(status_code=422, detail="description must be a string or null")

        if "completed" in data:
            completed = bool(data["completed"])

        if "priority" in data:
            priority = _priority_to_db(data["priority"])

        conn.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, completed = ?, priority = ?
            WHERE id = ?
            """,
            (title, description, int(completed), priority, task_id),
        )
        conn.commit()

        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    finally:
        conn.close()

    return _row_to_task(updated)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = _get_connection()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()

        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")

        return Response(status_code=204)
    finally:
        conn.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
```