```python
import asyncio
import datetime
import sqlite3
import uuid
import os
import sys
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing_extensions import Annotated

# Import required dependencies
from fastapi import APIRouter
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
import sqlite3 as sqlite3_lib

# Set up FastAPI app
app = FastAPI(
    title="Task Tracker API",
    description="REST API for tracking tasks",
    version="1.0.0"
)

# Create database engine
DATABASE_FILE = "tasks.db"

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        completed BOOLEAN DEFAULT FALSE,
        priority TEXT DEFAULT 'medium',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )")
    return conn

# Base class for tasks
BaseTask = declarative_base()

# Task model
class Task(BaseTask):
    def __init__(self, title: str, description: str = None, 
                 priority: str = "medium", completed: bool = False, 
                 created_at: datetime.datetime = None):
        self.title = title
        self.description = description
        self.priority = priority
        self.completed = completed
        self.created_at = created_at or datetime.datetime.now()

# Pydantic models
class CreateTaskInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    priority: str = Field(default="medium")

class PaginationResult:
    def __init__(self, items, total, page, page_size):
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size

# Routes
task_router = APIRouter(prefix="/tasks")

@app.post("/tasks", response_model=Task)
async def create_task(create_input: CreateTaskInput):
    db = get_db()
    try:
        task = Task(
            title=create_input.title,
            description=create_input.description,
            priority=create_input.priority,
            completed=False,
            created_at=datetime.datetime.now()
        )
        db.execute("INSERT INTO tasks (title, description, priority, completed, created_at) VALUES (?, ?, ?, ?, ?)",
                   (task.title, task.description, task.priority, task.completed, task.created_at))
        return task
    except sqlite3.Error as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.get("/tasks")
async def get_tasks(page=Query(default=1, ge=1), 
                      page_size=Query(default=10, ge=1), 
                      completed=Query(default=False)):
    db = get_db()
    cursor = db.cursor()
    params = []
    
    if completed:
        params.append("completed = :status")
        status = str(completed).lower() if completed else ""
        cursor.execute("SELECT * FROM tasks WHERE completed = ?", (status,))
    else:
        cursor.execute("SELECT * FROM tasks")

    items = []
    total = len([row for row in cursor.fetchall() if row[3]])
    
    cursor.execute("SELECT COUNT(*) as total FROM tasks")
    total = cursor.fetchone()[0]
    
    cursor.execute(f"SELECT id, title, description, priority, completed, created_at FROM tasks ORDER BY id ASC LIMIT :limit OFFSET :offset")
    page = int(Query.get("page", 1))
    page_size = int(Query.get("page_size", 10))
    offset = (page - 1) * page_size
    
    cursor.execute(f"SELECT * FROM tasks LIMIT :limit OFFSET :offset")
    for row in cursor.fetchall():
        items.append(Task(id=row[0], title=row[1], 
                           description=row[2], 
                           priority=row[3], 
                           completed=row[4],
                           created_at=datetime.datetime.fromisoformat(row[5])))
    
    items = Task.items
    return PaginationResult(items, total, page, page_size)

@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row:
        return Task(id=row[0], title=row[1], 
                   description=row[2], 
                   priority=row[3], 
                   completed=row[4],
                   created_at=datetime.datetime.fromisoformat(row[5]))
    return None

@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, update_input: CreateTaskInput):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("UPDATE tasks SET title=?, description=?, completed=?, priority=? WHERE id=?", (
            update_input.title or "", update_input.description, 
            update_input.completed, update_input.priority, task_id
        ))
        task = Task(id=task_id, title=update_input.title, 
                   description=update_input.description,
                   priority=update_input.priority, 
                   completed=update_input.completed, 
                   created_at=datetime.datetime.now())
        db.commit()
        return task
    except sqlite3.Error as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    if cursor.rowcount == 0:
        return HTTPException(status_code=404)
    db.commit()
    return None

if __name__ == "__main__":
    app.run()
```