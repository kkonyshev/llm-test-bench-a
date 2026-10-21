from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, constr
from typing import Optional, List
from datetime import datetime
import sqlite3
from sqlite3 import Connection
from contextlib import contextmanager

app = FastAPI()

DATABASE_URL = "tasks.db"
PRIORITY_OPTIONS = ["low", "medium", "high"]

class Task(BaseModel):
    id: int
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False
    priority: str = Field("medium", constr(to_lower=True))
    created_at: datetime = Field(default_factory=datetime.now)

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, constr(to_lower=True))

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = Field(None, constr(to_lower=True))

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed BOOLEAN DEFAULT FALSE,
                priority TEXT DEFAULT 'medium',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

init_db()

@app.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate):
    if task.priority and task.priority not in PRIORITY_OPTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Priority must be one of: low, medium, high"
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (title, description, priority, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            task.title.strip(),
            task.description,
            task.priority if task.priority else "medium",
            datetime.now().isoformat()
        ))
        conn.commit()
        task_id = cursor.lastrowid

    return Task(
        id=task_id,
        title=task.title.strip(),
        description=task.description,
        completed=False,
        priority=task.priority if task.priority else "medium",
        created_at=datetime.now()
    )

@app.get("/tasks", response_model=dict)
async def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
):
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Page must be >= 1"
        )
    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Page size must be between 1 and 100"
        )
    if priority and priority not in PRIORITY_OPTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Priority must be one of: low, medium, high"
        )

    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM tasks WHERE 1=1"
        params = []
        if completed is not None:
            query += " AND completed = ?"
            params.append(completed)
        if priority:
            query += " AND priority = ?"
            params.append(priority)

        cursor.execute(query, params)
        total = cursor.fetchone()[0]

        query = """
            SELECT id, title, description, completed, priority, created_at
            FROM tasks
            WHERE 1=1
        """
        params = []
        if completed is not None:
            query += " AND completed = ?"
            params.append(completed)
        if priority:
            query += " AND priority = ?"
            params.append(priority)
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"

        cursor.execute(query, params + [page_size, (page - 1) * page_size])
        tasks = cursor.fetchall()

    items = [
        Task(
            id=row[0],
            title=row[1],
            description=row[2],
            completed=row[3],
            priority=row[4],
            created_at=datetime.fromisoformat(row[5])
        )
        for row in tasks
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    return Task(
        id=row[0],
        title=row[1],
        description=row[2],
        completed=row[3],
        priority=row[4],
        created_at=datetime.fromisoformat(row[5])
    )

@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, task: TaskUpdate):
    if task.priority and task.priority not in PRIORITY_OPTIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Priority must be one of: low, medium, high"
        )

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        update_fields = []
        params = []

        if task.title is not None:
            update_fields.append("title = ?")
            params.append(task.title.strip())
        if task.description is not None:
            update_fields.append("description = ?")
            params.append(task.description)
        if task.completed is not None:
            update_fields.append("completed = ?")
            params.append(task.completed)
        if task.priority is not None:
            update_fields.append("priority = ?")
            params.append(task.priority)

        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No fields to update"
            )

        query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
        params.append(task_id)
        cursor.execute(query, params)
        conn.commit()

        cursor.execute("SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()

    return Task(
        id=row[0],
        title=row[1],
        description=row[2],
        completed=row[3],
        priority=row[4],
        created_at=datetime.fromisoformat(row[5])
    )

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
