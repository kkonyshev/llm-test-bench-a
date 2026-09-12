import os
import sqlite3
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Query, HTTPException, Body, status, Path
from pydantic import BaseModel, Field, validator

app = FastAPI()

# --- Configuration ---
DB_FILE = "tasks.db"

# --- Pydantic Models ---

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = "medium"

    @validator("priority")
    def validate_priority(cls, v):
        allowed = ["low", "medium", "high"]
        if v not in allowed:
            raise ValueError("priority must be one of: low, medium, high")
        return v

    @validator("title")
    def validate_title(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    class Config:
        extra = "forbid"

class Task(TaskBase):
    id: int
    completed: bool = False
    created_at: str

# --- Database Helpers ---

def get_db_connection():
    """Create a new database connection."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Access columns by name
    return conn

@app.on_event("startup")
def startup_event():
    """Initialize the database if it doesn't exist."""
    if not os.path.exists(DB_FILE):
        # ensure parent directory exists just in case, though SQLite creates file implicitly
        with get_db_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed INTEGER DEFAULT 0,
                    priority TEXT DEFAULT 'medium',
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

# --- Endpoints ---

@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: TaskCreate):
    """
    Create a new task.
    """
    with get_db_connection() as conn:
        created_at_str = datetime.utcnow().isoformat()
        # completed is 0 for False, 1 for True in SQLite integer representation
        completed_int = 1 if task.completed else 0
        
        cursor = conn.execute(
            "INSERT INTO tasks (title, description, priority, completed, created_at) VALUES (?, ?, ?, ?, ?)",
            (task.title, task.description, task.priority, completed_int, created_at_str)
        )
        conn.commit()
        task_id = cursor.lastrowid
        
        # Fetch the created row to return
        created_task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_task(created_task)

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page")
):
    """
    List tasks with optional filtering and pagination.
    """
    with get_db_connection() as conn:
        base_query = "SELECT * FROM tasks WHERE 1=1"
        count_query = "SELECT COUNT(*) as total FROM tasks WHERE 1=1"
        params = []
        count_params = []

        if completed is not None:
            # completed is stored as int 0/1, query param is bool
            base_query += " AND completed = ?"
            count_query += " AND completed = ?"
            params.append(int(completed))
            count_params.append(int(completed))

        if priority:
            base_query += " AND priority = ?"
            count_query += " AND priority = ?"
            params.append(priority)
            count_params.append(priority)

        # Get total count
        count_cursor = conn.execute(count_query, count_params)
        total = count_cursor.fetchone()["total"]

        # Get paginated items
        offset = (page - 1) * page_size
        items_query = base_query + " ORDER BY id ASC LIMIT ? OFFSET ?"
        items = conn.execute(items_query, params + [page_size, offset]).fetchall()

        return {
            "items": [_row_to_task(row) for row in items],
            "total": total,
            "page": page,
            "page_size": page_size
        }

@app.get("/tasks/{id}", response_model=Task)
def get_task(id: int = Path(..., description="Task ID")):
    """
    Retrieve a single task by ID.
    """
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        return _row_to_task(row)

@app.put("/tasks/{id}", response_model=Task)
def update_task(
    id: int = Path(..., description="Task ID"),
    update_data: TaskUpdate = Body(...)
):
    """
    Partially update a task.
    """
    with get_db_connection() as conn:
        # Check if task exists
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        # Prepare update values
        update_dict = update_data.dict(exclude_unset=True)
        
        # Validate manually if title or priority changed
        if "title" in update_dict:
            t = update_dict["title"].strip()
            if not t:
                raise HTTPException(status_code=422, detail="Title cannot be empty")
            update_dict["title"] = t

        if "priority" in update_dict:
            allowed = ["low", "medium", "high"]
            if update_dict["priority"] not in allowed:
                raise HTTPException(status_code=422, detail="Invalid priority")

        if not update_dict:
            # If no valid fields to update, return current task
            return _row_to_task(row)

        # Handle boolean to integer conversion
        if "completed" in update_dict:
            update_dict["completed"] = 1 if update_dict["completed"] else 0

        # Construct SET clause
        set_clauses = []
        values = []
        
        for key, value in update_dict.items():
            set_clauses.append(f"{key} = ?")
            values.append(value)
        
        # Always update updated_at? Spec doesn't require it, so skip.
        # Always include id in where clause
        values.append(id)

        update_sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        conn.execute(update_sql, values)
        conn.commit()

        # Fetch updated row
        updated_row = conn.execute("SELECT * FROM tasks WHERE id = ?", (id,)).fetchone()
        return _row_to_task(updated_row)

@app.delete("/tasks/{id}")
def delete_task(id: int = Path(..., description="Task ID")):
    """
    Delete a task by ID.
    """
    with get_db_connection() as conn:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        return None

# --- Helpers ---

def _row_to_task(row: sqlite3.Row) -> Task:
    """Convert sqlite3.Row to Task Pydantic model."""
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        priority=row["priority"],
        completed=bool(row["completed"]),
        created_at=row["created_at"]
    )
