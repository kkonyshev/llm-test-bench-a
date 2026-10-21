```python
from fastapi import FastAPI, HTTPException, status, Query, Body
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
import sqlite3
import os
from datetime import datetime

app = FastAPI()

# Database configuration
DB_FILE = "tasks.db"

def get_db_connection():
    """Create database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database and create table if not exists."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Pydantic models for validation
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"
    
    @validator('title', mode='before')
    def validate_title(cls, v: str):
        if not v or v.strip() == "":
            raise ValueError("Title must be non-empty")
        return v.strip()
    
    @validator('priority', mode='before')
    def validate_priority(cls, v: str):
        if v not in ["low", "medium", "high"]:
            raise ValueError("Priority must be one of 'low', 'medium', 'high'")
        return v

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    
    @validator('title', mode='after')
    def validate_title_after(cls, v: str):
        if not v or v.strip() == "":
            raise ValueError("Title must be non-empty")
        return v.strip()

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def root():
    return {"message": "Task Tracker API is running"}

@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, completed, priority) 
        VALUES (?, ?, 0, ?)
    ''', (task.title, task.description, task.priority))
    conn.commit()
    conn.close()
    
    # Fetch the created task to return full details
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM tasks WHERE id = (SELECT LAST_INSERT ROWID)
    ''')
    task_row = cursor.fetchone()
    conn.close()
    
    if not task_row:
        raise HTTPException(status_code=404, detail="Task creation failed")
    
    return TaskResponse(
        id=task_row["id"],
        title=task_row["title"],
        description=task_row["description"],
        completed=task_row["completed"],
        priority=task_row["priority"],
        created_at=task_row["created_at"]
    )

@app.get("/tasks")
def get_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1, le=100),
    page_size: int = Query(10, ge=1, le=100)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = "SELECT id, title, description, completed, priority, created_at FROM tasks ORDER BY id ASC"
    
    params = []
    
    if completed is not None:
        sql += " WHERE completed = ?"
        params.append(completed)
    
    if priority is not None:
        sql += " AND priority = ?"
        params.append(priority)
    
    cursor.execute(sql + " LIMIT ? OFFSET ?", (page_size, (page - 1) * page_size))
    tasks = cursor.fetchall()
    
    total = cursor.execute(sql).rowcount
    
    return {
        "items": [
            TaskResponse(
                id=t["id"],
                title=t["title"],
                description=t["description"],
                completed=t["completed"],
                priority=t["priority"],
                created_at=t["created_at"]
            )
            for t in tasks
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }
    
    conn.close()

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task_row = cursor.fetchone()
    conn.close()
    
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(
        id=task_row["id"],
        title=task_row["title"],
        description=task_row["description"],
        completed=task_row["completed"],
        priority=task_row["priority"],
        created_at=task_row["created_at"]
    )

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
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
        if task.priority not in ["low", "medium", "high"]:
            raise HTTPException(status_code=422, detail="Invalid priority")
        updates.append("priority = ?")
        params.append(task.priority)
    
    if not updates:
        raise HTTPException(status_code=400, detail="At least one field must be provided")
    
    sql = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
    params.append(task_id)
    
    cursor.execute(sql, params)
    conn.commit()
    
    # Fetch updated task
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task_row = cursor.fetchone()
    conn.close()
    
    if not task_row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(
        id=task_row["id"],
        title=task_row["title"],
        description=task_row["description"],
        completed=task_row["completed"],
        priority=task_row["priority"],
        created_at=task_row["created_at"]
    )

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    return None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```