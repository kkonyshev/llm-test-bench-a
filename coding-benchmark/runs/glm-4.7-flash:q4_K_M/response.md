```python
import sqlite3
from fastapi import FastAPI, Query, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from typing import Optional

# Application Setup
app = FastAPI()

# Database Configuration
DB_PATH = "tasks.db"


# Database Connection Helper
def get_connection():
    """Creates a database connection with row factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# Startup Event: Initialize Database and Table
@app.on_event("startup")
def startup_event():
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed BOOLEAN DEFAULT 0,
                priority TEXT NOT NULL DEFAULT 'medium',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


# --- Data Models ---

class Priority(str):
    """Custom validator for priority string."""
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if v not in ("low", "medium", "high"):
            raise ValueError("priority must be one of: low, medium, high")
        return v


class TaskBase(BaseModel):
    """Base schema for common task fields."""
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Priority = "medium"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        # Ensure non-empty after trim
        v = v.strip()
        if not v:
            raise ValueError("title cannot be empty")
        return v


class TaskCreate(TaskBase):
    """Schema for creating a task (no ID or created_at)."""
    pass


class TaskUpdate(BaseModel):
    """Schema for updating a task (all fields optional)."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Priority] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v):
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("title cannot be empty")
        return v


class TaskResponse(TaskBase):
    """Schema for returning a task object."""
    id: int
    completed: bool
    created_at: str

    class Config:
        from_attributes = True


# --- Database Operations ---

def create_task_db(task: TaskCreate):
    """Inserts a new task and returns the generated ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tasks (title, description, priority) VALUES (?, ?, ?)",
            (task.title, task.description, task.priority),
        )
        conn.commit()
        return cursor.lastrowid


def list_tasks_db(filters):
    """Fetches tasks based on filters and pagination."""
    conditions = []
    params = []

    if filters.get("completed") is not None:
        conditions.append("completed = ?")
        params.append(filters["completed"])

    if filters.get("priority"):
        conditions.append("priority = ?")
        params.append(filters["priority"])

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_connection() as conn:
        cursor = conn.cursor()

        # Count total matching records
        count_query = f"SELECT COUNT(*) as total FROM tasks WHERE {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()["total"]

        # Fetch paginated items
        page = filters.get("page", 1)
        page_size = filters.get("page_size", 10)
        offset = (page - 1) * page_size

        query = f"SELECT * FROM tasks WHERE {where_clause} ORDER BY id ASC LIMIT ? OFFSET ?"
        cursor.execute(query, params + [page_size, offset])
        rows = cursor.fetchall()

        return rows, total


def get_task_db(task_id: int):
    """Fetches a single task by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_task_db(task_id: int, task_update: TaskUpdate):
    """Updates a task partially. Returns False if task not found."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Check existence
        cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
        if not cursor.fetchone():
            return False

        # Build update query from provided fields only
        update_data = task_update.model_dump(exclude_unset=True)
        if not update_data:
            return True  # Nothing to update

        # Construct SQL
        set_clauses = ", ".join([f"{k} = ?" for k in update_data.keys()])
        values = list(update_data.values()) + [task_id]

        query = f"UPDATE tasks SET {set_clauses} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        return True


def delete_task_db(task_id: int):
    """Deletes a task. Returns True if deleted."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0


# --- REST Endpoints ---

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    """Creates a new task."""
    task_id = create_task_db(task)
    return get_task_db(task_id)


@app.get("/tasks", response_model=dict)
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    """Lists tasks with pagination and filtering."""
    # Validate priority filter manually for 422 response
    if priority and priority not in ("low", "medium", "high"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid priority value")

    filters = {
        "completed": completed,
        "priority": priority,
        "page": page,
        "page_size": page_size,
    }

    rows, total = list_tasks_db(filters)

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.get("/tasks/{id}", response_model=TaskResponse)
def get_task(id: int):
    """Gets a single task by ID."""
    task = get_task_db(id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@app.put("/tasks/{id}", response_model=TaskResponse)
def update_task(id: int, task_update: TaskUpdate):
    """Partially updates a task."""
    if not get_task_db(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    update_task_db(id, task_update)
    return get_task_db(id)


@app.delete("/tasks/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(id: int):
    """Deletes a task."""
    if not get_task_db(id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    delete_task_db(id)
```