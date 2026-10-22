from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
import sqlite3
from contextlib import contextmanager

app = FastAPI()

DATABASE_URL = "tasks.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
        """)
        conn.commit()

init_db()

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = "medium"

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError("Priority must be one of 'low', 'medium', 'high'")
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError("Priority must be one of 'low', 'medium', 'high'")
        return v

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str

class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title, description, priority, created_at) VALUES (?, ?, ?, ?)",
            (task.title.strip(), task.description, task.priority, datetime.utcnow().isoformat())
        )
        conn.commit()
        task_id = cursor.lastrowid
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return TaskResponse(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            completed=bool(row['completed']),
            priority=row['priority'],
            created_at=row['created_at']
        )

@app.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    if priority and priority not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=422, detail="Priority must be one of 'low', 'medium', 'high'")

    with get_db() as conn:
        query = "SELECT COUNT(*) FROM tasks WHERE 1=1"
        params = []
        if completed is not None:
            query += " AND completed = ?"
            params.append(1 if completed else 0)
        if priority:
            query += " AND priority = ?"
            params.append(priority)

        cursor = conn.cursor()
        cursor.execute(query, params)
        total = cursor.fetchone()[0]

        query = "SELECT * FROM tasks WHERE 1=1"
        if completed is not None:
            query += " AND completed = ?"
        if priority:
            query += " AND priority = ?"
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
        params += [page_size, (page - 1) * page_size]

        cursor.execute(query, params)
        rows = cursor.fetchall()

        items = [
            TaskResponse(
                id=row['id'],
                title=row['title'],
                description=row['description'],
                completed=bool(row['completed']),
                priority=row['priority'],
                created_at=row['created_at']
            ) for row in rows
        ]

        return TaskListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return TaskResponse(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            completed=bool(row['completed']),
            priority=row['priority'],
            created_at=row['created_at']
        )

@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task: TaskUpdate):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        existing_task = cursor.fetchone()
        if not existing_task:
            raise HTTPException(status_code=404, detail="Task not found")

        updates = {}
        if task.title is not None:
            updates['title'] = task.title.strip()
        if task.description is not None:
            updates['description'] = task.description
        if task.completed is not None:
            updates['completed'] = task.completed
        if task.priority is not None:
            updates['priority'] = task.priority

        if not updates:
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return TaskResponse(
                id=row['id'],
                title=row['title'],
                description=row['description'],
                completed=bool(row['completed']),
                priority=row['priority'],
                created_at=row['created_at']
            )

        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        query = f"UPDATE tasks SET {set_clause} WHERE id = ?"
        params = list(updates.values()) + [task_id]
        cursor.execute(query, params)
        conn.commit()

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return TaskResponse(
            id=row['id'],
            title=row['title'],
            description=row['description'],
            completed=bool(row['completed']),
            priority=row['priority'],
            created_at=row['created_at']
        )

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")
