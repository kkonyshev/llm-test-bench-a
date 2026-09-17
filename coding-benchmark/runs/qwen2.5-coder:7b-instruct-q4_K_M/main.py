from fastapi import FastAPI, HTTPException, Depends, Query
from pydantic import BaseModel, validator
from typing import List, Optional, Dict
from datetime import datetime
import sqlite3

app = FastAPI()

class Task(BaseModel):
    id: Optional[int]
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = 'medium'
    created_at: Optional[str] = None

    @validator('title')
    def title_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Title cannot be empty')
        return v

    @validator('priority')
    def priority_must_be_valid(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of low, medium, high')
        return v

    @validator('created_at', pre=True, always=True)
    def set_created_at(cls, v):
        if not v:
            return datetime.utcnow().isoformat()
        return v

def get_db_connection():
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.on_event('startup')
def create_tables():
    conn = get_db_connection()
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

@app.post('/tasks', response_model=Task, status_code=201)
def create_task(task: Task, db=Depends(get_db_connection)):
    task.created_at = datetime.utcnow().isoformat()
    cursor = db.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (task.title, task.description, task.completed, task.priority, task.created_at))
    db.commit()
    task.id = cursor.lastrowid
    return task

@app.get('/tasks', response_model=Dict)
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = Query(None, regex='^(low|medium|high)$'),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db=Depends(get_db_connection)
):
    cursor = db.cursor()
    query = 'SELECT * FROM tasks'
    params = []
    if completed is not None:
        query += ' WHERE completed = ?'
        params.append(completed)
    if priority is not None:
        if query.endswith('WHERE'):
            query += ' AND priority = ?'
        else:
            query += ' WHERE priority = ?'
        params.append(priority)
    query += ' ORDER BY id ASC LIMIT ? OFFSET ?'
    params.extend([page_size, (page - 1) * page_size])
    cursor.execute(query, params)
    items = [dict(row) for row in cursor.fetchall()]
    total = cursor.execute('SELECT COUNT(*) FROM tasks WHERE 1=1' + (' AND completed = ?' if completed is not None else '') + (' AND priority = ?' if priority is not None else ''), params).fetchone()[0]
    return {
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size
    }

@app.get('/tasks/{id}', response_model=Task, responses={404: {'detail': 'Task not found'}})
def get_task(id: int, db=Depends(get_db_connection)):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    else:
        raise HTTPException(status_code=404, detail='Task not found')

@app.put('/tasks/{id}', response_model=Task, responses={404: {'detail': 'Task not found'}, 422: {'detail': 'Validation error'}})
def update_task(id: int, task: Task, db=Depends(get_db_connection)):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
    row = cursor.fetchone()
    if row:
        updates = {k: v for k, v in task.dict().items() if v is not None}
        if 'title' in updates:
            validator('title')(updates['title'])
        if 'priority' in updates:
            validator('priority')(updates['priority'])
        set_clause = ', '.join([f'{k} = ?' for k in updates.keys()])
        update_params = tuple(updates.values()) + (id,)
        cursor.execute(f'UPDATE tasks SET {set_clause} WHERE id = ?', update_params)
        db.commit()
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
        updated_task = dict(cursor.fetchone())
        return updated_task
    else:
        raise HTTPException(status_code=404, detail='Task not found')

@app.delete('/tasks/{id}', status_code=204, responses={404: {'detail': 'Task not found'}})
def delete_task(id: int, db=Depends(get_db_connection)):
    cursor = db.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
    row = cursor.fetchone()
    if row:
        cursor.execute('DELETE FROM tasks WHERE id = ?', (id,))
        db.commit()
    else:
        raise HTTPException(status_code=404, detail='Task not found')
