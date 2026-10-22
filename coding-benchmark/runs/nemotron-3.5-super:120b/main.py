from fastapi import FastAPI, HTTPException, Path, Query, status
from pydantic import BaseModel
from typing import Optional
import sqlite3
from datetime import datetime, timezone

app = FastAPI()

DB_PATH = "tasks.db"
VALID_PRIORITIES = {"low", "medium", "high"}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
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


init_db()


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


def _row_to_task(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["completed"] = bool(item["completed"])
    return item


@app.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskOut)
def create_task(task: TaskCreate):
    title = task.title.strip() if task.title else ""
    if not title:
        raise HTTPException(status_code=422, detail="title must not be empty")
    if len(title) > 200:
        raise HTTPException(status_code=422, detail="title must be at most 200 characters")
    priority = task.priority
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")

    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, task.description, 0, priority, created_at),
    )
    conn.commit()
    task_id = cur.lastrowid
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return _row_to_task(row)


@app.get("/tasks", response_model=dict)
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    if priority is not None and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")

    conn = get_db()
    conditions = []
    params = []
    if completed is not None:
        conditions.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    base_query = "SELECT * FROM tasks"
    count_query = "SELECT COUNT(*) FROM tasks"
    if conditions:
        where = " WHERE " + " AND ".join(conditions)
        base_query += where
        count_query += where

    total = conn.execute(count_query, params).fetchone()[0]

    query = base_query + " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = conn.execute(query, params).fetchall()
    conn.close()

    items = [_row_to_task(row) for row in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int = Path(...)):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _row_to_task(row)


@app.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, task: TaskUpdate):
    conn = get_db()
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")

    updates = {}
    if task.title is not None:
        title = task.title.strip()
        if not title:
            conn.close()
            raise HTTPException(status_code=422, detail="title must not be empty")
        if len(title) > 200:
            conn.close()
            raise HTTPException(status_code=422, detail="title must be at most 200 characters")
        updates["title"] = title
    if task.description is not None:
        updates["description"] = task.description
    if task.priority is not None:
        if task.priority not in VALID_PRIORITIES:
            conn.close()
            raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")
        updates["priority"] = task.priority
    if task.completed is not None:
        updates["completed"] = 1 if task.completed else 0

    if updates:
        set_clause = ", ".join(f"{key} = ?" for key in updates)
        values = list(updates.values()) + [task_id]
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        conn.commit()

    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    conn.close()
    return _row_to_task(row)


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int = Path(...)):
    conn = get_db()
    cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return None
