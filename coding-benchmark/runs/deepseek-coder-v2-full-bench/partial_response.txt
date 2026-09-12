 ```python
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, validator
from typing import Optional, List
import sqlite3
from datetime import datetime
import uvicorn

app = FastAPI()

DATABASE_URL = "tasks.db"

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"

    @validator('title')
    def title_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Title must not be empty')
        return v

    @validator('priority')
    def priority_must_be_valid(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of low, medium, high')
        return v

class Task(TaskCreate):
    id: int
    completed: bool = False
    created_at: str

def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, priority, created_at)
        VALUES (?, ?, ?, ?)
    ''', (task.title, task.description, task.priority, datetime.now().isoformat()))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {
        "id": task_id,
        "title": task.title,
        "description": task.description,
        "completed": False,
        "priority": task.priority,
        "created_at": datetime.now().isoformat()
    }

@app.get("/tasks", status_code=200)
def list_tasks(completed: Optional[bool] = None, priority: Optional[str] = None, page: int = 1, page_size: int = 10):
    if page < 1:
        raise HTTPException(status_code=422, detail="Page must be greater than or equal to 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=422, detail="Page size must be between 1 and 100")
    if priority is not None and priority not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=422, detail="Priority must be one of low, medium, high")

    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM tasks"
    params = []
    if completed is not None:
        query += " WHERE completed = ?"
        params.append(completed)
    if priority is not None:
        if completed is not None:
            query += " AND priority = ?"
        else:
            query += " WHERE priority = ?"
        params.append(priority)
    query += " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    cursor.execute(query, params)
    tasks = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total = cursor.fetchone()[0]
    conn.close()
    return {
        "items": [dict(task) for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}", status_code=200)
def get_task(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    task = cursor.fetchone()
    conn.close()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return dict(task)

@app.put("/tasks/{id}", status_code=200)
def update_task(id: int, task_update: TaskCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    task = cursor.fetchone()
    if task is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_fields = {}
    if task_update.title:
        update_fields['title'] = task_update.title
    if task_update.description is not None:
        update_fields['description'] = task_update.description
    if task_update.priority:
        update_fields['priority'] = task_update.priority

    query = "UPDATE tasks SET "
    params = []
    for key, value in update_fields.items():
        query += f"{key} = ?, "
        params.append(value)
    query = query.rstrip(", ") + " WHERE id = ?"
    params.append(id)
    cursor.execute(query, params)
    conn.commit()
    conn.close()

    updated_task = get_task(id)
    return updated_task

@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    task = cursor.fetchone()
    if task is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    cursor.execute("DELETE FROM tasks WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```