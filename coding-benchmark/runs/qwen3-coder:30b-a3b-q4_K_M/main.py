import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, validator, Field
from enum import Enum

app = FastAPI()

# Database setup
def init_db():
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT FALSE,
            priority TEXT DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class PriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: PriorityEnum = PriorityEnum.medium

    @validator('title')
    def title_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Title must not be empty')
        return v.strip()

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[PriorityEnum] = None

    @validator('title')
    def title_must_not_be_empty(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Title must not be empty')
        return v.strip() if v else None

class Task(TaskBase):
    id: int
    completed: bool = False
    created_at: str

    class Config:
        orm_mode = True

class TaskListResponse(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int

def get_task_by_id(task_id: int) -> Optional[Task]:
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id=?", (task_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    
    return Task(
        id=row[0],
        title=row[1],
        description=row[2],
        completed=bool(row[3]),
        priority=row[4],
        created_at=row[5]
    )

def get_tasks_paginated(
    completed: Optional[bool] = None,
    priority: Optional[PriorityEnum] = None,
    page: int = 1,
    page_size: int = 10
) -> TaskListResponse:
    if page < 1:
        raise HTTPException(status_code=422, detail="Page must be >= 1")
    
    if not 1 <= page_size <= 100:
        raise HTTPException(status_code=422, detail="Page size must be between 1 and 100")

    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Build WHERE clause
    where_conditions = []
    params = []
    
    if completed is not None:
        where_conditions.append("completed = ?")
        params.append(int(completed))
        
    if priority is not None:
        where_conditions.append("priority = ?")
        params.append(priority.value)
        
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    # Count total
    count_query = f"SELECT COUNT(*) FROM tasks WHERE {where_clause}"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]
    
    # Get paginated items
    offset = (page - 1) * page_size
    select_query = f"SELECT * FROM tasks WHERE {where_clause} ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([page_size, offset])
    cursor.execute(select_query, params)
    
    rows = cursor.fetchall()
    conn.close()
    
    items = [Task(
        id=row[0],
        title=row[1],
        description=row[2],
        completed=bool(row[3]),
        priority=row[4],
        created_at=row[5]
    ) for row in rows]
    
    return TaskListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size
    )

@app.post("/tasks", status_code=201, response_model=Task)
def create_task(task: TaskCreate):
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    created_at = datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, ?, ?, ?)",
        (
            task.title,
            task.description,
            False,
            task.priority.value,
            created_at
        )
    )
    
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return Task(
        id=task_id,
        title=task.title,
        description=task.description,
        completed=False,
        priority=task.priority.value,
        created_at=created_at
    )

@app.get("/tasks", response_model=TaskListResponse)
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[PriorityEnum] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    return get_tasks_paginated(completed, priority, page, page_size)

@app.get("/tasks/{id}", response_model=Task)
def read_task(id: int):
    task = get_task_by_id(id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.put("/tasks/{id}", response_model=Task)
def update_task(id: int, task_update: TaskUpdate):
    existing_task = get_task_by_id(id)
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")

    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    
    # Prepare update fields
    set_clause_parts = []
    params = []
    
    if task_update.title is not None:
        set_clause_parts.append("title = ?")
        params.append(task_update.title)
        
    if task_update.description is not None:
        set_clause_parts.append("description = ?")
        params.append(task_update.description)
        
    if task_update.completed is not None:
        set_clause_parts.append("completed = ?")
        params.append(int(task_update.completed))
        
    if task_update.priority is not None:
        set_clause_parts.append("priority = ?")
        params.append(task_update.priority.value)
    
    if not set_clause_parts:
        # No updates provided
        conn.close()
        return existing_task
    
    set_clause = ", ".join(set_clause_parts)
    params.append(id)
    
    cursor.execute(f"UPDATE tasks SET {set_clause} WHERE id=?", params)
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
        
    conn.commit()
    conn.close()
    
    return get_task_by_id(id)

@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):
    conn = sqlite3.connect('tasks.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id=?", (id,))
    
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
        
    conn.commit()
    conn.close()
