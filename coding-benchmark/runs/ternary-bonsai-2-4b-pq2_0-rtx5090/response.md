```python
from fastapi import FastAPI, HTTPException, Query, Body
from datetime import datetime
import sqlite3
import os
from typing import Optional, Dict, Any

app = FastAPI()

DATABASE_FILE = "tasks.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# Priority validation
VALID_PRIORITIES = ["low", "medium", "high"]

@app.on_event("startup")
def startup_event():
    init_db()

@app.post("/tasks", status_code=201)
def create_task(title: str, description: Optional[str] = None, priority: Optional[str] = "medium"):
    # Validate title
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required and cannot be empty")
    
    # Validate priority
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="Priority must be one of: low, medium, high")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO tasks (title, description, completed, priority)
        VALUES (?, ?, 0, ?)
        """,
        (title, description, priority)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Create response object
    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "completed": False,
        "priority": priority,
        "created_at": datetime.now().isoformat()
    }
    
    return task

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(None, description="Filter by completion state"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page")
):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build query
    params = []
    where_clause = []
    
    if completed is not None:
        where_clause.append("completed = ?")
        params.append(completed)
    if priority is not None:
        if priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=422, detail="Priority must be one of: low, medium, high")
        where_clause.append("priority = ?")
        params.append(priority)
    
    if where_clause:
        query = "SELECT * FROM tasks WHERE " + ", ".join(where_clause)
    else:
        query = "SELECT * FROM tasks ORDER BY id ASC"
    
    cursor.execute(query, params)
    all_tasks = cursor.fetchall()
    
    total = len(all_tasks)
    items_per_page = page_size
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    
    paginated_tasks = all_tasks[start_index:end_index]
    
    response = {
        "items": [{"id": t["id"], "title": t["title"], "description": t["description"], "completed": t["completed"], "priority": t["priority"], "created_at": t["created_at"]} for t in paginated_tasks],
        "total": total,
        "page": page,
        "page_size": page_size
    }
    
    conn.close()
    return response

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_obj = {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"],
        "completed": task["completed"],
        "priority": task["priority"],
        "created_at": task["created_at"]
    }
    return task_obj

@app.put("/tasks/{task_id}")
def update_task(task_id: int, title: Optional[str] = None, description: Optional[str] = None, completed: Optional[bool] = None, priority: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if title is not None:
        title = title.strip()
        if not title:
            raise HTTPException(status_code=422, detail="Title is required and cannot be empty")
    
    if priority is not None:
        if priority not in VALID_PRIORITIES:
            raise HTTPException(status_code=422, detail="Priority must be one of: low, medium, high")
    
    params = []
    updates = []
    
    if title is not None:
        updates.append("title = ?")
        params.append(title)
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if completed is not None:
        updates.append("completed = ?")
        params.append(completed)
    if priority is not None:
        updates.append("priority = ?")
        params.append(priority)
    
    if not updates:
        raise HTTPException(status_code=400, detail="At least one field must be updated")
    
    updates_str = ", ".join(updates)
    cursor.execute(
        "UPDATE tasks SET " + updates_str + " WHERE id = ?",
        params + [task_id]
    )
    conn.commit()
    conn.close()
    
    # Fetch updated task
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        # Should have updated, but maybe ID mismatch - return error anyway
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_obj = {
        "id": task["id"],
        "title": task["title"],
        "description": task["description"],
        "completed": task["completed"],
        "priority": task["priority"],
        "created_at": task["created_at"]
    }
    return task_obj

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    return {}
```