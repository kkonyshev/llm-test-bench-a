import sqlite3
from datetime import datetime, timezone
from typing import List, Optional, Literal

from fastapi import FastAPI, HTTPException, Path, Query, Body
from pydantic import BaseModel, Field


app = FastAPI()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Literal["low", "medium", "high"] = "medium"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Literal["low", "medium", "high"]] = None


class TaskListResponse(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int


@app.post("/tasks", status_code=201, response_model=Task)
def create_task(task: TaskCreate):
    if not task.title or not task.title.strip():
        raise HTTPException(status_code=422, detail="title must be non-empty after trimming")

    title = task.title.strip()
    description = task.description
    priority = task.priority
    completed = False
    created_at = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    cursor = conn.execute(
        "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (title, description, int(completed), priority, created_at),
    )
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()

    return Task(
        id=task_id,
        title=title,
        description=description,
        completed=completed,
        priority=priority,
        created_at=created_at,
    )


@app.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    if priority is not None and priority not in ("low", "medium", "high"):
        raise HTTPException(status_code=422, detail="priority must be one of: low, medium, high")

    conn = get_conn()

    query = "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE 1=1"
    params: List = []
    if completed is not None:
        query += " AND completed = ?"
        params.append(1 if completed else 0)
    if priority is not None:
        query += " AND priority = ?"
        params.append(priority)

    count_query = f"SELECT COUNT(*) FROM ({query})"
    total = conn.execute(count_query, params).fetchone()[0]

    offset = (page - 1) * page_size
    query += " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([page_size, offset])

    rows = conn.execute(query, params).fetchall()
    conn.close()

    items = [Task(**dict(row)) for row in rows]

    return TaskListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int = Path(...)):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    conn.close()

    if row is None:
        raise HTTPException(status_code=404, detail="task not found")

    return Task(**dict(row))


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int = Path(...), task_update: Optional[TaskUpdate] = Body(default=None)):
    conn = get_conn()
    row = conn.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="task not found")

    current = dict(row)

    if task_update is not None:
        if task_update.title is not None:
            if not task_update.title.strip():
                conn.close()
                raise HTTPException(status_code=422, detail="title must be non-empty after trimming")
            if len(task_update.title) > 200:
                conn.close()
                raise HTTPException(status_code=422, detail="title must be at most 200 characters")
            current["title"] = task_update.title.strip()

        if task_update.description is not None:
            current["description"] = task_update.description

        if task_update.completed is not None:
            current["completed"] = task_update.completed

        if task_update.priority is not None:
            if task_update.priority not in ("low", "medium", "high"):
                conn.close()
                raise HTTPException(status_code=422, detail="priority must be one of: low, medium, high")
            current["priority"] = task_update.priority

    conn.execute(
        "UPDATE tasks SET title = ?, description = ?, completed = ?, priority = ? WHERE id = ?",
        (
            current["title"],
            current["description"],
            int(current["completed"]),
            current["priority"],
            task_id,
        ),
    )
    conn.commit()

    row = conn.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,),
    ).fetchone()
    conn.close()

    return Task(**dict(row))


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int = Path(...)):
    conn = get_conn()
    row = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="task not found")

    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return None
