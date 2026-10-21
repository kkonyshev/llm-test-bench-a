from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import sqlite3
from contextlib import contextmanager
from datetime import datetime
import uvicorn

app = FastAPI()

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
DB_FILE = "tasks.db"
VALID_PRIORITIES = ["low", "medium", "high"]

# -----------------------------------------------------------------------------
# Pydantic Models
# -----------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = Field(default="medium", regex="^(low|medium|high)$")

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = Field(default=None, regex="^(low|medium|high)$")

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str

class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int

# -----------------------------------------------------------------------------
# Database Helper
# -----------------------------------------------------------------------------

@contextmanager
def get_db():
    """Context manager to handle SQLite connections."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    """Initialize the database schema on startup."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL CHECK(length(trim(title)) > 0),
            description TEXT,
            completed INTEGER DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

# -----------------------------------------------------------------------------
# Startup Event
# -----------------------------------------------------------------------------

@app.on_event("startup")
def startup_event():
    init_db()

# -----------------------------------------------------------------------------
# Utility: Convert Row to Model
# -----------------------------------------------------------------------------

def _row_to_task(row: sqlite3.Row) -> TaskResponse:
    return TaskResponse(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        completed=bool(row["completed"]),
        priority=row["priority"],
        created_at=row["created_at"]
    )

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

# POST /tasks
@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate):
    """Create a new task."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title, description, priority) VALUES (?, ?, ?)",
            (task.title, task.description, task.priority)
        )
        conn.commit()
        task_id = cursor.lastrowid

        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        new_row = cursor.fetchone()

        if not new_row:
            raise HTTPException(status_code=500, detail="Failed to retrieve created task")
        
        return _row_to_task(new_row)

# GET /tasks
@app.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    """List tasks with optional filtering and pagination."""
    # Validate priority if provided
    if priority is not None and priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority value")

    with get_db() as conn:
        cursor = conn.cursor()
        
        conditions = []
        params = []

        if completed is not None:
            conditions.append("completed = ?")
            params.append(1 if completed else 0)

        if priority is not None:
            conditions.append("priority = ?")
            params.append(priority)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM tasks WHERE {where_clause}"
        cursor.execute(count_sql, params)
        total = cursor.fetchone()["total"]

        # Get paginated items
        offset = (page - 1) * page_size
        items_sql = f"SELECT * FROM tasks WHERE {where_clause} ORDER BY id ASC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])
        cursor.execute(items_sql, params)
        rows = cursor.fetchall()

        items = [_row_to_task(r) for r in rows]

        return TaskListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )

# GET /tasks/{id}
@app.get("/tasks/{id}", response_model=TaskResponse)
def get_task(id: int):
    """Get a specific task by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Task not found")

        return _row_to_task(row)

# PUT /tasks/{id}
@app.put("/tasks/{id}", response_model=TaskResponse)
def update_task(id: int, task_update: TaskUpdate):
    """Update a specific task by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Check existence
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Task not found")

        # Prepare update data
        update_data = task_update.dict(exclude_unset=True)
        if not update_data:
            # If no fields were provided, return current task
            return get_task(id)

        # Validate priority if provided in update
        if "priority" in update_data and update_data["priority"] not in VALID_PRIORITIES:
            raise HTTPException(status_code=422, detail="Invalid priority value")

        # Validate title if provided (non-empty)
        if "title" in update_data and not update_data["title"].strip():
            raise HTTPException(status_code=422, detail="Title cannot be empty")

        # Build SQL
        set_clauses = []
        values = []
        for field, value in update_data.items():
            set_clauses.append(f"{field} = ?")
            values.append(value)

        values.append(id) # Add ID for WHERE clause
        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        
        cursor.execute(sql, values)
        conn.commit()

        return get_task(id)

# DELETE /tasks/{id}
@app.delete("/tasks/{id}")
def delete_task(id: int):
    """Delete a specific task by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Task not found")
            
        conn.commit()
        return JSONResponse(status_code=204)

# Entry point (optional, for running directly)
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
