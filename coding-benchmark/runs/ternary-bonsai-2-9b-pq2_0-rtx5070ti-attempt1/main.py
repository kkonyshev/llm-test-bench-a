import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import sys
import os

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    created_at: str

class TaskResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

VALID_PRIORITIES = {"low", "medium", "high"}
db_path = "tasks.db"

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_task(task_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    conn.close()
    return None

def create_task(title, description=None, priority="medium", completed=False):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, description, 1 if completed else 0, priority, datetime.now().isoformat()))
    task_id = cursor.lastrowid
    cursor.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "completed": row[3],
        "priority": row[4],
        "created_at": row[5]
    }

def list_tasks(completed=None, priority=None, page=1, page_size=10):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    sql = "SELECT * FROM tasks ORDER BY id ASC"
    params = []
    if completed is not None:
        sql += " WHERE completed = ?"
        params.append(completed)
    if priority is not None:
        sql += " AND priority = ?"
        params.append(priority)
    
    cursor.execute(sql, params)
    tasks = [dict(row) for row in cursor.fetchall()]
    total = len(tasks)
    conn.close()
    return {"items": tasks, "total": total, "page": page, "page_size": page_size}

def get_one(task_id):
    row = get_task(task_id)
    if row:
        return row
    raise HTTPException(status_code=404, detail="Task not found")

def update_one(task_id, title=None, description=None, completed=None, priority=None):
    row = get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    values = []
    if title is not None:
        values.append("title = ?")
        params.append(title)
    if description is not None:
        values.append("description = ?")
        params.append(description)
    if completed is not None:
        values.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        values.append("priority = ?")
        params.append(priority)
    
    if values:
        sql = "UPDATE tasks SET " + ", ".join(values) + " WHERE id = ?"
        params.append(task_id)
        cursor.execute(sql, params)
    conn.commit()
    return get_task(task_id)

def delete_one(task_id):
    get_task(task_id)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
