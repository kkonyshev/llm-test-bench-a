```python
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, status, Query
from pydantic import BaseModel, Field, validator

app = FastAPI()

# Database setup
DATABASE = "tasks.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed BOOLEAN NOT NULL DEFAULT 0,
                priority TEXT NOT NULL DEFAULT 'medium',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()

init_db()

# Models
class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = "medium"

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('priority must be one of low, medium, high')
        return v

class TaskCreate(TaskBase):
    pass

class Task(TaskBase):
    id: int
    completed: bool
    created_at: str

    class Config:
        from_attributes = True

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator('priority')
    def validate_priority(cls, v):
        if v is not None and v not in ['low', 'medium', 'high']:
            raise ValueError('priority must be one of low, medium, high')
        return v

# CRUD operations
def get_task_by_id(conn, task_id: int) -> Optional[Dict[str, Any]]:
    cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    return dict(row) if row else None

def create_task(conn, task: TaskCreate) -> Task:
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (task.title, task.description, False, task.priority, now)
    )
    task_id = cursor.lastrowid
    return get_task_by_id(conn, task_id)

def update_task(conn, task_id: int, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    task = get_task_by_id(conn, task_id)
    if not task:
        return None

    updates = []
    params = []
    for key, value in update_data.items():
        if value is not None:
            updates.append(f"{key} = ?")
            params.append(value)

    if not updates:
        return task

    params.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    return get_task_by_id(conn, task_id)

def delete_task(conn, task_id: int) -> bool:
    task = get_task_by_id(conn, task_id)
    if not task:
        return False
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return True

def get_tasks(conn, completed: Optional[bool] = None, priority: Optional[str] = None,
              page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    query = "SELECT * FROM tasks WHERE 1=1"
    params = []

    if completed is not None:
        query += " AND completed = ?"
        params.append(1 if completed else 0)

    if priority is not None:
        query += " AND priority = ?"
        params.append(priority)

    query += " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])

    cursor = conn.execute(query, params)
    items = [dict(row) for row in cursor.fetchall()]

    # Get total count for pagination
    count_query = "SELECT COUNT(*) FROM tasks WHERE 1=1"
    count_params = []
    if completed is not None:
        count_query += " AND completed = ?"
        count_params.append(1 if completed else 0)
    if priority is not None:
        count_query += " AND priority = ?"
        count_params.append(priority)

    total = conn.execute(count_query, count_params).fetchone()[0]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size
    }

# Endpoints
@app.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=Task)
def create_task_endpoint(task: TaskCreate):
    with get_db() as conn:
        created_task = create_task(conn, task)
        if not created_task:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return created_task

@app.get("/tasks", response_model=Dict[str, Any])
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = Query(None, regex="^(low|medium|high)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    with get_db() as conn:
        return get_tasks(conn, completed, priority, page, page_size)

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    with get_db() as conn:
        task = get_task_by_id(conn, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return task

@app.put("/tasks/{task_id}", response_model=Task)
def update_task_endpoint(task_id: int, task_update: TaskUpdate):
    with get_db() as conn:
        update_data = task_update.model_dump(exclude_unset=True)
        updated_task = update_task(conn, task_id, update_data)
        if not updated_task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        return updated_task

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_endpoint(task_id: int):
    with get_db() as conn:
        if not delete_task(conn, task_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
```