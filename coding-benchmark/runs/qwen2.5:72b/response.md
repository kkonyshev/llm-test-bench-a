```python
import sqlite3
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field, validator

app = FastAPI()

DATABASE = 'tasks.db'

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = 'medium'

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of "low", "medium", "high"')
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of "low", "medium", "high"')
        return v

class Task(TaskCreate):
    id: int
    completed: bool = False
    created_at: str

    class Config:
        orm_mode = True

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
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

@app.on_event("startup")
def startup():
    init_db()

@app.post("/tasks", response_model=Task, status_code=201)
def create_task(task: TaskCreate):
    conn = get_db()
    created_at = datetime.utcnow().isoformat()
    cursor = conn.execute('''
        INSERT INTO tasks (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (task.title.strip(), task.description, task.completed, task.priority, created_at))
    conn.commit()
    task_id = cursor.lastrowid
    conn.close()
    return get_task(task_id)

@app.get("/tasks", response_model=dict)
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    conn = get_db()
    query = 'SELECT * FROM tasks'
    params = []
    filters = []

    if completed is not None:
        filters.append('completed = ?')
        params.append(completed)
    if priority is not None:
        filters.append('priority = ?')
        params.append(priority)

    if filters:
        query += ' WHERE ' + ' AND '.join(filters)

    query += ' ORDER BY id ASC LIMIT ? OFFSET ?'
    params.extend([page_size, (page - 1) * page_size])

    cursor = conn.execute(query, params)
    tasks = [Task(**dict(row)) for row in cursor.fetchall()]
    total = conn.execute('SELECT COUNT(*) FROM tasks' + (' WHERE ' + ' AND '.join(filters) if filters else ''), params[:-2]).fetchone()[0]
    conn.close()
    return {
        "items": tasks,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    conn.close()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return Task(**dict(task))

@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task_update: TaskUpdate):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = task_update.dict(exclude_unset=True)
    update_fields = ', '.join([f"{k} = ?" for k in update_data.keys()])
    params = list(update_data.values()) + [task_id]

    if update_fields:
        conn.execute(f'UPDATE tasks SET {update_fields} WHERE id = ?', params)
        conn.commit()

    conn.close()
    return get_task(task_id)

@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int):
    conn = get_db()
    cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
```