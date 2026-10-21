from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from datetime import datetime
import sqlite3
import uuid

# Model definitions
class TaskCreateModel(BaseModel):
    title: str
    description: str = None
    priority: str = "medium"

class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    completed: bool
    priority: str
    created_at: datetime

class TaskListQueryParams(BaseModel):
    completed: bool = False
    priority: str = "medium"
    page: int = 1
    page_size: int = 10

class TaskGetQueryParams(BaseModel):
    id: int = None
    page: int = 1
    page_size: int = 10

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect("tasks.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        completed INTEGER DEFAULT 0,
        priority TEXT DEFAULT 'medium',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )")
    conn.commit()
    conn.close()

@app.get("/")
async def root():
    return {"message": "Task Tracker API"}

@app.post("/tasks")
async def create_task(task_create: TaskCreateModel):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        created = {
            "title": task_create.title,
            "description": task_create.description,
            "completed": False,
            "priority": task_create.priority
        }
        cursor.execute(
            "INSERT INTO tasks (title, description, completed, priority) VALUES (?, ?, ?, ?)",
            created["title"], created["description"], created["completed"], created["priority"]
        )
        new_id = cursor.lastrowid
        created["id"] = new_id
        created["created_at"] = datetime.fromisoformat(created["created_at"])
        conn.commit()
        return TaskResponse(**created)
    except sqlite3.Error as e:
        raise HTTPException(status_code=status.HTTP_422_BAD_REQUEST, detail=str(e))
    finally:
        conn.close()

@app.get("/tasks")
async def get_tasks(task_list: TaskListQueryParams = Query(default=TaskListQueryParams(page=1, page_size=10), completed=None, priority=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        params = {
            "completed": bool(completed),
            "priority": priority if priority else None,
            "page": task_list.page if task_list.page else 1,
            "page_size": task_list.page_size if task_list.page_size <= 100 else None
        }
        
        query = f"SELECT * FROM tasks WHERE {cursor.column_names[0]} IN ({'completed' if completed else ''} {params['completed']})"
        if params['priority']:
            query = f"SELECT * FROM tasks WHERE {cursor.column_names[1]} = {params['priority']}"
        
        cursor.execute(query, params)
        tasks = cursor.fetchall()
        total = cursor.rowcount
        page = task_list.page
        page_size = task_list.page_size if task_list.page_size <= 100 else None
        
        return TaskListResponse(items=tasks, total=total, page=page, page_size=page_size)
    except sqlite3.Error as e:
        raise HTTPException(status_code=status.HTTP_422_BAD_REQUEST, detail=str(e))
    finally:
        conn.close()

@app.get("/tasks/{task_id}")
async def get_task(task_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        if row:
            return TaskResponse(**row)
        raise HTTPException(status_code=404, detail="Task not found")
    except sqlite3.Error as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    finally:
        conn.close()

@app.put("/tasks/{task_id}")
async def update_task(task_id: int, task_update: TaskCreateModel = Field(...)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE tasks SET title=?, description=?, completed=?, priority=? WHERE id=?", (
            task_update.title, task_update.description, task_update.completed, task_update.priority, task_id
        ))
        return TaskResponse(**cursor.lastrowid)
    except sqlite3.Error as e:
        raise HTTPException(status_code=status.HTTP_422_BAD_REQUEST, detail=str(e))
    finally:
        conn.close()

@app.delete("/tasks/{task_id}")
async def delete_task(task_id: int):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return 204
    except sqlite3.Error as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    finally:
        conn.close()
