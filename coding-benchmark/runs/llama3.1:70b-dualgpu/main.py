import os
import sqlite3
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, validator, ValidationError, root_validator
from typing import Optional, List
from datetime import datetime

app = FastAPI()

# Create a connection to the SQLite database
conn = sqlite3.connect('tasks.db')
cursor = conn.cursor()

# Create the tasks table if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        completed INTEGER NOT NULL DEFAULT 0,
        priority TEXT NOT NULL DEFAULT 'medium',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
''')
conn.commit()

# Data model: Task
class Task(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str

    class Config:
        orm_mode = True

    @root_validator(pre=True)
    def check_title(cls, values):
        if not values['title'].strip():
            raise ValueError('Title is required and cannot be empty')
        return values

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Invalid priority value')
        return v

# Endpoints
@app.post('/tasks', response_model=Task, status_code=201)
def create_task(task: Task):
    try:
        cursor.execute('INSERT INTO tasks (title, description, completed, priority) VALUES (?, ?, ?, ?)',
                       (task.title, task.description, task.completed, task.priority))
        conn.commit()
        task.id = cursor.lastrowid
        task.created_at = datetime.now().isoformat()
        return task
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

@app.get('/tasks', response_model=List[Task])
def list_tasks(completed: Optional[bool] = None, priority: Optional[str] = None, page: int = 1, page_size: int = 10):
    try:
        query = 'SELECT * FROM tasks'
        params = []
        if completed is not None:
            query += ' WHERE completed = ?'
            params.append(int(completed))
        if priority:
            if 'WHERE' not in query:
                query += ' WHERE'
            else:
                query += ' AND'
            query += ' priority = ?'
            params.append(priority)
        query += ' ORDER BY id ASC LIMIT ? OFFSET ?'
        params.extend([page_size, (page - 1) * page_size])
        cursor.execute(query, params)
        tasks = [Task(**row) for row in cursor.fetchall()]
        total = cursor.execute('SELECT COUNT(*) FROM tasks', params[:-2]).fetchone()[0]
        return {'items': tasks, 'total': total, 'page': page, 'page_size': page_size}
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

@app.get('/tasks/{id}', response_model=Task)
def get_task(id: int):
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
    task = cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404)
    return Task(**task)

@app.put('/tasks/{id}', response_model=Task)
def update_task(id: int, task: Task):
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
    existing_task = cursor.fetchone()
    if not existing_task:
        raise HTTPException(status_code=404)
    try:
        updated_task = Task(**{**existing_task, **task.dict(exclude_unset=True)})
        cursor.execute('UPDATE tasks SET title = ?, description = ?, completed = ?, priority = ? WHERE id = ?',
                       (updated_task.title, updated_task.description, updated_task.completed, updated_task.priority, id))
        conn.commit()
        return updated_task
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors())

@app.delete('/tasks/{id}')
def delete_task(id: int):
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
    task = cursor.fetchone()
    if not task:
        raise HTTPException(status_code=404)
    cursor.execute('DELETE FROM tasks WHERE id = ?', (id,))
    conn.commit()
    return Response(status_code=204)
