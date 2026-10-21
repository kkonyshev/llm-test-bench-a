from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
import sqlite3
from datetime import datetime, timezone

app = FastAPI()

DB_PATH = "tasks.db"
PRIORITY_CHOICES = {"low", "medium", "high"}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup():
    init_db()


def validate_title(title: str):
    stripped = title.strip()
    if not stripped:
        raise HTTPException(status_code=422, detail="Title must be non-empty after trim")
    if len(stripped) > 200:
        raise HTTPException(status_code=422, detail="Title must be at most 200 characters")


def validate_priority(p: str):
    if p not in PRIORITY_CHOICES:
        raise HTTPException(status_code=422, detail="Invalid priority value")


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None


@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    validate_title(task.title)
    if task.priority is None:
        priority = "medium"
    else:
        validate_priority(task.priority)
        priority = task.priority
    created_at = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, 0, ?, ?)",
        (task.title, task.description, priority, created_at),
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return {
        "id": task_id,
        "title": task.title,
        "description": task.description,
        "completed": False,
        "priority": priority,
        "created_at": created_at,
    }


@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    conn = get_conn()
    cur = conn.cursor()
    conditions = []
    params = []
    if completed is not None:
        conditions.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        if priority not in PRIORITY_CHOICES:
            raise HTTPException(status_code=422, detail="Invalid priority value")
        conditions.append("priority = ?")
        params.append(priority)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    cur.execute(f"SELECT COUNT(*) FROM tasks {where}", params)
    total = cur.fetchone()[0]
    offset = (page - 1) * page_size
    cur.execute(
        f"SELECT * FROM tasks {where} ORDER BY id ASC LIMIT ? OFFSET ?",
        params + [page_size, offset],
    )
    rows = cur.fetchall()
    conn.close()
    items = []
    for row in rows:
        items.append(
            {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "completed": bool(row[3]),
                "priority": row[4],
                "created_at": row[5],
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@app.get("/tasks/{id}")
def get_task(id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "completed": bool(row[3]),
        "priority": row[4],
        "created_at": row[5],
    }


@app.put("/tasks/{id}")
def update_task(id: int, task: TaskUpdate):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    updates = []
    params = []
    if task.title is not None:
        validate_title(task.title)
        updates.append("title = ?")
        params.append(task.title)
    if task.description is not None:
        updates.append("description = ?")
        params.append(task.description)
    if task.completed is not None:
        updates.append("completed = ?")
        params.append(1 if task.completed else 0)
    if task.priority is not None:
        validate_priority(task.priority)
        updates.append("priority = ?")
        params.append(task.priority)
    params.append(id)
    cur.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    row = cur.fetchone()
    conn.close()
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "completed": bool(row[3]),
        "priority": row[4],
        "created_at": row[5],
    }


@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    cur.execute("DELETE FROM tasks WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return None
