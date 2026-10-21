from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
from typing import Optional, List
import sqlite3
import os

app = FastAPI()

db_file = "tasks.db"

def get_db_connection():
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

# Task Schema
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str

# Validate priority
VALID_PRIORITIES = ["low", "medium", "high"]

def validate_title(title: str):
    if not title or len(title) > 200:
        raise ValueError("Title must be 1-200 characters and not empty")

@app.post("/tasks")
def create_task(task: TaskCreate):
    validate_title(task.title)
    if task.priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="Priority must be one of 'low', 'medium', 'high'")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO tasks (title, description, completed, priority, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            task.title,
            task.description,
            False,
            task.priority,
            datetime.now().isoformat()
        ))
        conn.commit()
        
        cursor.execute('''
            SELECT * FROM tasks WHERE id = (SELECT LAST_INSERT_ROWID())
        ''')
        new_task = cursor.fetchone()
        
        if new_task:
            return TaskResponse(
                id=new_task["id"],
                title=new_task["title"],
                description=new_task["description"],
                completed=new_task["completed"],
                priority=new_task["priority"],
                created_at=new_task["created_at"]
            )
        raise HTTPException(status_code=500, detail="Task creation failed")
    finally:
        conn.close()

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
):
    # Validate page and page_size
    if page < 1:
        raise HTTPException(status_code=422, detail="Page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=422, detail="Page size must be 1-100")
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="Priority must be one of 'low', 'medium', 'high'")
    
    # Build query
    where_clause = "1"
    params = []
    
    if completed is not None:
        where_clause += " AND completed = ?"
        params.append(completed)
    
    if priority is not None:
        where_clause += " AND priority = ?"
        params.append(priority)
    
    cursor = get_db_connection()
    conn = conn
    
    query = f"SELECT * FROM tasks WHERE {where_clause} ORDER BY id ASC"
    cursor.execute(query, params)
    tasks = cursor.fetchall()
    
    # Pagination
    total = len(tasks)
    page_size = page_size
    
    start = (page - 1) * page_size
    end = start + page_size
    paginated_tasks = tasks[start:end]
    
    conn.close()
    
    return {
        "items": [
            {
                "id": t["id"],
                "title": t["title"],
                "description": t["description"],
                "completed": t["completed"],
                "priority": t["priority"],
                "created_at": t["created_at"]
            }
            for t in paginated_tasks
        ],
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}")
def get_task(id: int):
    cursor = get_db_connection()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,))
    task = cursor.fetchone()
    
    if not task:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    
    conn.close()
    return TaskResponse(
        id=task["id"],
        title=task["title"],
        description=task["description"],
        completed=task["completed"],
        priority=task["priority"],
        created_at=task["created_at"]
    )

@app.put("/tasks/{id}")
def update_task(id: int, task_update: TaskUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Update only provided fields
        fields = []
        params = []
        
        if task_update.title is not None:
            fields.append("title")
            params.append(task_update.title)
        
        if task_update.description is not None:
            fields.append("description")
            params.append(task_update.description)
        
        if task_update.completed is not None:
            fields.append("completed")
            params.append(1 if task_update.completed else 0)
        
        if task_update.priority is not None:
            fields.append("priority")
            params.append(task_update.priority)
        
        if not fields:
            raise HTTPException(status_code=400, detail="At least one field must be updated")
        
        where_clause = "id = ?"
        params.append(id)
        query = f"UPDATE tasks SET {', '.join(fields)} WHERE {where_clause}"
        
        cursor.execute(query, params)
        conn.commit()
        
        # Fetch updated task
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,))
        task = cursor.fetchone()
        
        if not task:
            conn.close()
            raise HTTPException(status_code=404, detail="Task not found")
        
        conn.close()
        return TaskResponse(
            id=task["id"],
            title=task["title"],
            description=task["description"],
            completed=task["completed"],
            priority=task["priority"],
            created_at=task["created_at"]
        )
    finally:
        conn.close()

@app.delete("/tasks/{id}")
def delete_task(id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("DELETE FROM tasks WHERE id = ?", (id,))
        conn.commit()
        
        conn.close()
        return None
    finally:
        conn.close()
