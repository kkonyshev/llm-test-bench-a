"""Task Tracker API — FastAPI + SQLite."""

from contextlib import asynccontextmanager
from typing import Optional

import sqlite3
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, field_validator


VALID_PRIORITIES = ("low", "medium", "high")
DB_FILE = "tasks.db"

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    completed INTEGER NOT NULL DEFAULT 0,
    priority TEXT NOT NULL DEFAULT 'medium',
    created_at TEXT NOT NULL
)"""


def create_tables() -> None:
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        conn.close()


def get_db():
    """Yield a sqlite3 connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_FILE)
    # Ensure the table exists even if the app lifespan did not run.
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(row):
    return {key: row[key] for key in row.keys()}


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"

    @field_validator("title")
    def validate_title(cls, value):
        value = value.strip()
        if not value or len(value) > 200:
            raise ValueError("title must be a non-empty string of at most 200 characters")
        return value

    @field_validator("priority")
    def validate_priority(cls, value):
        if value not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {', '.join(VALID_PRIORITIES)}")
        return value


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @field_validator("title")
    def validate_title(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value or len(value) > 200:
            raise ValueError("title must be a non-empty string of at most 200 characters")
        return value

    @field_validator("priority")
    def validate_priority(cls, value):
        if value is not None and value not in VALID_PRIORITIES:
            raise ValueError(f"priority must be one of {', '.join(VALID_PRIORITIES)}")
        return value


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(lifespan=lifespan)


@app.post("/tasks", status_code=201, response_model=TaskResponse)
async def create_task(task: TaskCreate, db: sqlite3.Connection = Depends(get_db)):
    now = datetime.now().isoformat()
    db.execute(
        "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (task.title, task.description, False, task.priority, now),
    )
    db.commit()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (db.lastrowid,)).fetchone()
    return TaskResponse(**row_to_dict(row))


@app.get("/tasks", status_code=200)
async def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db: sqlite3.Connection = Depends(get_db),
):
    if priority is not None and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be at least 1")
    if not 1 <= page_size <= 100:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 100 inclusive")

    conditions = []
    params = []
    if completed is not None:
        conditions.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    where = ""
    if conditions:
        where = " WHERE " + " AND ".join(conditions)

    total = db.execute(f"SELECT COUNT(*) FROM tasks{where}", params).fetchone()[0]

    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT id, title, description, completed, priority, created_at "
        f"FROM tasks{where} ORDER BY id ASC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    ).fetchall()

    return {
        "items": [TaskResponse(**row_to_dict(row)) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/tasks/{id}", status_code=200)
async def get_task(id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse(**row_to_dict(row))


@app.put("/tasks/{id}", status_code=200)
async def update_task(id: int, task: TaskUpdate, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")

    data = {}
    for field in ("title", "description", "completed", "priority"):
        value = getattr(task, field)
        if value is not None:
            data[field] = value

    if data:
        set_clause = ", ".join(f"{key} = ?" for key in data)
        db.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?",
            list(data.values()) + [id],
        )
        db.commit()

    updated = db.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    return TaskResponse(**row_to_dict(updated))


@app.delete("/tasks/{id}", status_code=204)
async def delete_task(id: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    db.execute("DELETE FROM tasks WHERE id = ?", (id,))
    db.commit()
    return None
