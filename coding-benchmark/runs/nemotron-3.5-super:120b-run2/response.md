```python
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator

DB_PATH = "tasks.db"

app = FastAPI(title="Task Tracker API")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.on_event("startup")
def startup() -> None:
    conn = get_conn()
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


def row_to_task(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "completed": bool(row["completed"]),
        "priority": row["priority"],
        "created_at": row["created_at"],
    }


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        if len(v) > 200:
            raise ValueError("title must be at most 200 characters")
        if not v.strip():
            raise ValueError("title must not be empty")
        return v

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            raise ValueError("priority must be one of low, medium, high")
        return v


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if len(v) > 200:
            raise ValueError("title must be at most 200 characters")
        if not v.strip():
            raise ValueError("title must not be empty")
        return v

    @field_validator("priority")
    @classmethod
    def _validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in ("low", "medium", "high"):
            raise ValueError("priority must be one of low, medium, high")
        return v


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: datetime


class TaskList(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int


ALLOWED_PRIORITIES = ("low", "medium", "high")


@app.post("/tasks", status_code=201, response_model=Task)
def create_task(task_in: TaskCreate):
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (task_in.title, task_in.description, 0, task_in.priority, now),
    )
    conn.commit()
    task_id = cur.lastrowid
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row_to_task(row)


@app.get("/tasks", response_model=TaskList)
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    if priority is not None and priority not in ALLOWED_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority")

    conn = get_conn()
    conditions: List[str] = []
    params: list = []

    if completed is not None:
        conditions.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    where_sql = (" WHERE " + " AND ".join(conditions)) if conditions else ""

    total_row = conn.execute(
        f"SELECT COUNT(*) FROM tasks{where_sql}", params
    ).fetchone()
    total = total_row[0]

    query = f"SELECT * FROM tasks{where_sql} ORDER BY id ASC LIMIT ? OFFSET ?"
    offset = (page - 1) * page_size
    rows = conn.execute(query, params + [page_size, offset]).fetchall()
    conn.close()

    items = [row_to_task(row) for row in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return row_to_task(row)


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task_in: TaskUpdate):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_in.model_dump(exclude_unset=True)
    if update_data:
        set_parts = []
        values = []
        for field, value in update_data.items():
            if field == "completed":
                set_parts.append("completed = ?")
                values.append(1 if value else 0)
            else:
                set_parts.append(f"{field} = ?")
                values.append(value)
        values.append(task_id)
        conn.execute(
            f"UPDATE tasks SET {', '.join(set_parts)} WHERE id = ?", values
        )
        conn.commit()

    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return row_to_task(row)


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return None
```