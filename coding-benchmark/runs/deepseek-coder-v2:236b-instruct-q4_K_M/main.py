from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import sqlite3
import os

app = FastAPI()

# Database setup
DB_NAME = "tasks.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

if not os.path.exists(DB_NAME):
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
else:
    conn = get_db_connection()

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

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator('title')
    def title_must_not_be_empty(cls, v):
        if v and not v.strip():
            raise ValueError('Title must not be empty')
        return v

    @validator('priority')
    def priority_must_be_valid(cls, v):
        if v and v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of low, medium, high')
        return v

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: datetime

@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, priority, created_at)
        VALUES (?, ?, ?, ?)
    ''', (task.title, task.description, task.priority, datetime.now().isoformat()))
    conn.commit()
    task_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return get_task(task_id)

@app.get("/tasks", status_code=200)
def list_tasks(completed: Optional[bool] = None, priority: Optional[str] = None, page: int = 1, page_size: int = 10):
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=422, detail="Invalid page or page_size")
    if priority and priority not in ['low', 'medium', 'high']:
        raise HTTPException(status_code=422, detail="Invalid priority")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM tasks"
    params = []
    if completed is not None:
        query += " WHERE completed = ?"
        params.append(completed)
    if priority:
        if completed is not None:
            query += " AND priority = ?"
        else:
            query += " WHERE priority = ?"
        params.append(priority)
    query += " ORDER BY id ASC"
    total = len(cursor.execute(query, params).fetchall())
    query += " LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    tasks = cursor.execute(query, params).fetchall()
    cursor.close()
    conn.close()
    return {
        "items": [Task(**dict(task)) for task in tasks],
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}", status_code=200)
def get_task(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    task = cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    cursor.close()
    conn.close()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return Task(**dict(task))

@app.put("/tasks/{id}", status_code=200)
def update_task(id: int, task_update: TaskUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    task = cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
    if task is None:
        cursor.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = task_update.dict(exclude_unset=True)
    if "title" in update_data:
        cursor.execute("UPDATE tasks SET title = ? WHERE id = ?", (update_data["title"], id))
    if "description" in update_data:
        cursor.execute("UPDATE tasks SET description = ? WHERE id = ?", (update_data["description"], id))
    if "completed" in update_data:
        cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (update_data["completed"], id))
    if "priority" in update_data:
        cursor.execute("UPDATE tasks SET priority = ? WHERE id = ?", (update_data["priority"], id))
    conn.commit()
    cursor.close()
    conn.close()
    return get_task(id)

@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (id,))
    conn.commit()
    cursor.close()
    conn.close()
