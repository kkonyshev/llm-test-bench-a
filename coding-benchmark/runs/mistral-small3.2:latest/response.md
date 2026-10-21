```python
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Annotated
from datetime import datetime
import sqlite3
from sqlite3 import Connection
from contextlib import contextmanager

app = FastAPI()

DATABASE_URL = "tasks.db"

class Task(BaseModel):
    id: int
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    created_at: datetime

    @validator("priority")
    def validate_priority(cls, v):
        if v not in ["low", "medium", "high"]:
            raise ValueError("priority must be one of 'low', 'medium', 'high'")
        return v

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = "medium"

    @validator("priority")
    def validate_priority(cls, v):
        if v not in ["low", "medium", "high"]:
            raise ValueError("priority must be one of 'low', 'medium', 'high'")
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator("priority")
    def validate_priority(cls, v):
        if v is not None and v not in ["low", "medium", "high"]:
            raise ValueError("priority must be one of 'low', 'medium', 'high'")
        return v

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

@app.post("/tasks", response_model=Task, status_code=201)
async def create_task(task: TaskCreate):
    created_at = datetime.now().isoformat()
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (title, description, priority, created_at)
            VALUES (?, ?, ?, ?)
        """, (task.title, task.description, task.priority, created_at))
        conn.commit()
        task_id = cursor.lastrowid
    return Task(
        id=task_id,
        title=task.title,
        description=task.description,
        completed=False,
        priority=task.priority,
        created_at=datetime.fromisoformat(created_at)
    )

@app.get("/tasks", response_model=dict)
async def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
):
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 100")
    if priority is not None and priority not in ["low", "medium", "high"]:
        raise HTTPException(status_code=422, detail="priority must be one of 'low', 'medium', 'high'")

    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM tasks WHERE 1=1"
        params = []
        if completed is not None:
            query += " AND completed = ?"
            params.append(completed)
        if priority is not None:
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
        if priority is not None:
            query += " AND priority = ?"
            params.append(priority)
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([page_size, (page - 1) * page_size])
        cursor.execute(query, params)
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

@app.get("/tasks/{id}", response_model=Task)
async def get_task(id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return Task(
            id=row[0],
            title=row[1],
            description=row[2],
            completed=row[3],
            priority=row[4],
            created_at=datetime.fromisoformat(row[5])
        )

@app.put("/tasks/{id}", response_model=Task)
async def update_task(id: int, task: TaskUpdate):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Task not found")

        updates = []
        params = []
        if task.title is not None:
            updates.append("title = ?")
            params.append(task.title)
        if task.description is not None:
            updates.append("description = ?")
            params.append(task.description)
        if task.completed is not None:
            updates.append("completed = ?")
            params.append(task.completed)
        if task.priority is not None:
            updates.append("priority = ?")
            params.append(task.priority)

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        params.append(id)
        cursor.execute(query, params)
        conn.commit()

        cursor.execute("SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?", (id,))
        row = cursor.fetchone()
        return Task(
            id=row[0],
            title=row[1],
            description=row[2],
            completed=row[3],
            priority=row[4],
            created_at=datetime.fromisoformat(row[5])
        )

@app.delete("/tasks/{id}", status_code=204)
async def delete_task(id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Task not found")
        cursor.execute("DELETE FROM tasks WHERE id = ?", (id,))
        conn.commit()
```