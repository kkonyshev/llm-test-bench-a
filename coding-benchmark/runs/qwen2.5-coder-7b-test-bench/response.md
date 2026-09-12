```python
from fastapi import FastAPI, HTTPException, Query, Body
from pydantic import BaseModel, validator
from datetime import datetime
import sqlite3

app = FastAPI()

class TaskIn(BaseModel):
    title: str
    description: str = None
    completed: bool = False
    priority: str = "medium"

    @validator('title')
    def title_must_be_non_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Title cannot be empty')
        if len(v) > 200:
            raise ValueError('Title must be at most 200 characters')
        return v

    @validator('priority')
    def priority_must_be_valid(cls, v):
        if v not in ["low", "medium", "high"]:
            raise ValueError('Priority must be one of low, medium, high')
        return v

class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    completed: bool
    priority: str
    created_at: datetime

    class Config:
        orm_mode = True

class TaskDB:
    def __init__(self):
        self.con = sqlite3.connect('tasks.db')
        self.con.row_factory = sqlite3.Row
        self.setup_db()

    def setup_db(self):
        with self.con:
            self.con.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed BOOLEAN NOT NULL DEFAULT 0,
                    priority TEXT NOT NULL DEFAULT 'medium',
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def get_tasks(self, completed=None, priority=None, page=1, page_size=10):
        query = 'SELECT * FROM tasks'
        params = []
        if completed is not None:
            query += ' WHERE completed = ?'
            params.append(completed)
        if priority is not None:
            if query.endswith('WHERE'):
                query += ' AND'
            else:
                query += ' WHERE'
            query += ' priority = ?'
            params.append(priority)
        if page_size < 1 or page_size > 100:
            raise HTTPException(status_code=422, detail='Page size must be between 1 and 100')
        offset = (page - 1) * page_size
        query += ' LIMIT ? OFFSET ?'
        params.extend([page_size, offset])
        tasks = self.con.execute(query, params).fetchall()
        return [TaskOut(**dict(task)) for task in tasks]

    def get_task(self, task_id):
        task = self.con.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail='Task not found')
        return TaskOut(**dict(task))

    def create_task(self, task_in: TaskIn):
        task = task_in.dict()
        task['created_at'] = datetime.utcnow().isoformat()
        with self.con:
            self.con.execute('INSERT INTO tasks (title, description, completed, priority, created_at) VALUES (?, ?, ?, ?, ?)',
                             (task['title'], task['description'], task['completed'], task['priority'], task['created_at']))
            task['id'] = self.con.lastrowid
        return TaskOut(**task)

    def update_task(self, task_id, task_in: TaskIn):
        task = task_in.dict(exclude_unset=True)
        if task:
            set_clause = ', '.join([f"{k} = ?" for k in task.keys()])
            params = list(task.values()) + [task_id]
            with self.con:
                self.con.execute(f'UPDATE tasks SET {set_clause} WHERE id = ?', params)
        else:
            raise HTTPException(status_code=400, detail='No updates provided')
        task = self.get_task(task_id)
        return task

    def delete_task(self, task_id):
        with self.con:
            self.con.execute('DELETE FROM tasks WHERE id = ?', (task_id,))

task_db = TaskDB()

@app.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(task_in: TaskIn):
    return task_db.create_task(task_in)

@app.get("/tasks", response_model=dict)
def list_tasks(completed: bool = None, priority: str = None, page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100)):
    tasks = task_db.get_tasks(completed, priority, page, page_size)
    total = len(tasks_db.get_tasks())
    return {
        "items": tasks,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}", response_model=TaskOut)
def get_task(id: int):
    return task_db.get_task(id)

@app.put("/tasks/{id}", response_model=TaskOut)
def update_task(id: int, task_in: TaskIn):
    return task_db.update_task(id, task_in)

@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):
    task_db.delete_task(id)
```