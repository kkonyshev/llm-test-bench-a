import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, ValidationError
from fastapi import FastAPI, HTTPException, Query, status
import sys
import os

# FastAPI app instance
app = FastAPI()

# Database connection setup
DATABASE_URL = "tasks.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE_URL)
    return conn

def init_database():
    """Initialize the SQLite database and create tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def create_db_connection():
    """Get database connection."""
    return get_db_connection()

# Task request model
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Title must be 1-200 chars")
    description: Optional[str] = Field(None, description="Optional description")
    priority: Optional[str] = Field(None, description="Priority must be one of: low, medium, high")

# Task response model (includes auto-generated fields)
class Task(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str

# Task filter model for GET /tasks
class TaskFilter(BaseModel):
    completed: Optional[bool] = None
    priority: Optional[str] = None
    page: int = Field(..., ge=1, description="Page number, must be >= 1")
    page_size: int = Field(..., ge=1, le=100, description="Page size, must be 1-100")

# Helper function to get task by id
def get_task_by_id(db, task_id: int):
    cursor = db.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return row

# Helper function to get all tasks with filters
def get_tasks_with_filters(db, filters: Dict[str, Any]) -> List[Dict]:
    cursor = db.cursor()
    
    sql = "SELECT * FROM tasks ORDER BY id ASC"
    params = []
    
    if filters.get("completed") is not None:
        sql += " WHERE completed = ?"
        params.append(filters["completed"])
    
    if filters.get("priority") is not None:
        sql += " AND priority = ?"
        params.append(filters["priority"])
    
    if "page" in filters and "page_size" in filters:
        offset = (filters["page"] - 1) * filters["page_size"]
        sql += " LIMIT ? OFFSET ?"
        params.append(filters["page_size"])
        params.append(offset)
    
    cursor.execute(sql, params)
    tasks = cursor.fetchall()
    
    total_count = len(tasks)
    
    return [dict(row) for row in tasks]

@app.post("/tasks")
def create_task(task: TaskCreate):
    """Create a new task."""
    conn = create_db_connection()
    cursor = conn.cursor()
    
    try:
        # Validate priority
        if task.priority is not None:
            if task.priority not in ["low", "medium", "high"]:
                raise HTTPException(status_code=422, detail="Priority must be one of: low, medium, high")
        else:
            task.priority = "medium"  # Default priority
        
        cursor.execute('''
            INSERT INTO tasks (title, description, priority, completed, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            task.title,
            task.description,
            task.priority,
            False,  # completed defaults to false
            datetime.now().isoformat()
        ))
        
        task_id = cursor.lastrowid
        
        result = Task(
            id=task_id,
            title=task.title,
            description=task.description,
            completed=False,
            priority=task.priority,
            created_at=datetime.now().isoformat()
        )
        
        conn.commit()
        return result
        
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        conn.close()

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    """List all tasks with optional filters."""
    conn = create_db_connection()
    
    try:
        filters = {
            "completed": completed,
            "priority": priority
        }
        
        tasks = get_tasks_with_filters(conn, filters)
        
        result = {
            "items": [Task(
                id=t["id"],
                title=t["title"],
                description=t.get("description"),
                completed=bool(t["completed"]),
                priority=t["priority"],
                created_at=t["created_at"]
            ) for t in tasks],
            "total": len(tasks),
            "page": page,
            "page_size": page_size
        }
        
        return result
        
    finally:
        conn.close()

@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Get a single task by id."""
    conn = create_db_connection()
    
    try:
        task_data = get_task_by_id(conn, task_id)
        
        return Task(
            id=task_data[0],
            title=task_data[1],
            description=task_data[2],
            completed=bool(task_data[3]),
            priority=task_data[4],
            created_at=task_data[5]
        )
        
    except HTTPException:
        raise
    finally:
        conn.close()

@app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskCreate):
    """Update a task with optional fields."""
    conn = create_db_connection()
    cursor = conn.cursor()
    
    try:
        # Validate priority if provided
        if task.priority is not None:
            if task.priority not in ["low", "medium", "high"]:
                raise HTTPException(status_code=422, detail="Priority must be one of: low, medium, high")
        
        # Check if task exists
        existing = get_task_by_id(conn, task_id)
        
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Build update statement with existing fields that aren't changed
        fields_to_update = []
        params = []
        
        if task.title is not None:
            fields_to_update.append("title")
            params.append(task.title)
        
        if task.description is not None:
            fields_to_update.append("description")
            params.append(task.description)
        
        if task.priority is not None:
            fields_to_update.append("priority")
            params.append(task.priority)
        
        if task.completed is not None:
            fields_to_update.append("completed")
            params.append(1 if task.completed else 0)
        
        if task.created_at is not None:
            fields_to_update.append("created_at")
            params.append(task.created_at)
        
        if fields_to_update:
            set_clause = ", ".join(fields_to_update)
            cursor.execute(
                f"UPDATE tasks SET {set_clause} WHERE id = ?",
                (task_id,) + params
            )
        else:
            # No fields to update - task already up to date
            pass
        
        conn.commit()
        
        # Get the updated task
        updated = get_task_by_id(conn, task_id)
        
        return Task(
            id=updated[0],
            title=updated[1],
            description=updated[2],
            completed=bool(updated[3]),
            priority=updated[4],
            created_at=updated[5]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    """Delete a task by id."""
    conn = create_db_connection()
    
    try:
        # Check if task exists
        existing = get_task_by_id(conn, task_id)
        
        if existing is None:
            raise HTTPException(status_code=404, detail="Task not found")
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        
        return status.HTTP_204_NO_CONTENT
        
    finally:
        conn.close()

# Initialize database on startup
init_database()
