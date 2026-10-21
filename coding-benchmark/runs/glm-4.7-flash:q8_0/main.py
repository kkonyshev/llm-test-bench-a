import os
import sqlite3
from datetime import datetime
from typing import Optional, Literal
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationError

app = FastAPI()

DB_PATH = "tasks.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


@app.on_event("startup")
def startup_event():
    init_db()


# --- Pydantic Models ---

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def validate_title(self):
        # Trim and check empty
        self.title = self.title.strip()
        if len(self.title) == 0:
            raise ValueError("Title cannot be empty")
        # Check max length
        if len(self.title) > 200:
            raise ValueError("Title must be 200 characters or less")
        return self

    class Config:
        json_schema_extra = {
            "examples": [
                {"title": "Buy milk", "description": "2%", "priority": "high"}
            ]
        }


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[Literal["low", "medium", "high"]] = None

    @model_validator(mode="after")
    def validate_title_if_provided(self):
        if self.title is not None:
            self.title = self.title.strip()
            if len(self.title) == 0:
                raise ValueError("Title cannot be empty")
            if len(self.title) > 200:
                raise ValueError("Title must be 200 characters or less")
        return self

    @model_validator(mode="after")
    def validate_priority_if_provided(self):
        if self.priority is not None and self.priority not in ["low", "medium", "high"]:
            raise ValueError("Priority must be one of: low, medium, high")
        return self


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str  # ISO 8601 string

    class Config:
        from_attributes = True


# --- Endpoints ---

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    now = datetime.utcnow().isoformat()
    
    cursor.execute(
        "INSERT INTO tasks (title, description, priority, created_at) VALUES (?, ?, ?, ?)",
        (task.title, task.description, task.priority, now)
    )
    conn.commit()
    
    task_id = cursor.lastrowid
    
    # Fetch the created task to return full object
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    return TaskResponse.model_validate(row)


class TaskListParams(BaseModel):
    completed: Optional[bool] = None
    priority: Optional[Literal["low", "medium", "high"]] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=100)


@app.get("/tasks", response_model=dict)
def list_tasks(params: TaskListParams = Query(...)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build WHERE clause based on filters
    where_clauses = []
    query_params = []
    
    if params.completed is not None:
        # Convert bool to int for SQLite
        where_clauses.append("completed = ?")
        query_params.append(1 if params.completed else 0)
        
    if params.priority:
        where_clauses.append("priority = ?")
        query_params.append(params.priority)
    
    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
    
    # Total Count Query
    count_query = f"SELECT COUNT(*) as total FROM tasks WHERE {where_sql}"
    cursor.execute(count_query, query_params)
    total = cursor.fetchone()["total"]
    
    # Pagination
    offset = (params.page - 1) * params.page_size
    select_query = f"SELECT * FROM tasks WHERE {where_sql} ORDER BY id ASC LIMIT ? OFFSET ?"
    cursor.execute(select_query, query_params + [params.page_size, offset])
    rows = cursor.fetchall()
    conn.close()
    
    items = [TaskResponse.model_validate(row) for row in rows]
    
    return {
        "items": items,
        "total": total,
        "page": params.page,
        "page_size": params.page_size
    }


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
    return TaskResponse.model_validate(row)


@app.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task_update: TaskUpdate):
    # Check existence first to match spec 404 behavior
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
    # Build dynamic update query
    update_data = {k: v for k, v in task_update.model_dump(exclude_unset=True).items()}
    
    if not update_data:
        # No changes requested
        conn.close()
        return get_task(task_id)

    set_clauses = []
    params = []
    
    # SQLite columns map: completed is int, priority is str, created_at is not updatable usually, but let's ignore it for update
    # Note: We exclude 'created_at' from updates just in case
    if "title" in update_data:
        set_clauses.append("title = ?")
        params.append(update_data["title"])
    if "description" in update_data:
        set_clauses.append("description = ?")
        params.append(update_data["description"])
    if "completed" in update_data:
        set_clauses.append("completed = ?")
        params.append(1 if update_data["completed"] else 0)
    if "priority" in update_data:
        set_clauses.append("priority = ?")
        params.append(update_data["priority"])
    
    # Always append id at the end
    params.append(task_id)
    
    update_query = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
    cursor.execute(update_query, params)
    conn.commit()
    
    # Fetch updated row
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    return TaskResponse.model_validate(row)


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    
    return None
