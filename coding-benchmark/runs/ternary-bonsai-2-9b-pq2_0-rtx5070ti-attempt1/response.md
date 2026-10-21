```python
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
import os
from typing import Optional, List, Tuple, Dict


class TaskModel(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


class TaskResponse(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int


# Initialize FastAPI app
app = FastAPI()

# Task database helper
class TaskDatabase:
    def __init__(self, db_path: str = "tasks.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database table if not exists."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                priority TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    
    def create_task(self, title: str, description: Optional[str] = None,
                    priority: Optional[str] = "medium",
                    completed: bool = False) -> Tuple[int, Task]:
        """Create a new task and return it."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO tasks (title, description, completed, priority, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, description, 0 if not completed else 1, priority, created_at))
        
        task_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute(
            "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
            (task_id,)
        )
        row = cursor.fetchone()
        
        conn.close()
        
        return task_id, Task(
            id=row[0],
            title=row[1],
            description=row[2],
            completed=row[3],
            priority=row[4],
            created_at=row[5]
        )
    
    def get_tasks(self, 
                  completed: Optional[bool] = None,
                  priority: Optional[str] = None,
                  page: int = 1,
                  page_size: int = 10) -> Tuple[Task, int, int, int]:
        """Get tasks with pagination and filters."""
        sql = "SELECT * FROM tasks ORDER BY id ASC"
        params = []
        
        if completed is not None:
            sql += " WHERE completed = ?"
            params.append(completed)
        if priority is not None:
            sql += " AND priority = ?"
            params.append(priority)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(sql, params)
        tasks = cursor.fetchall()
        
        # Calculate total
        total_sql = sql if not params else sql
        cursor.execute(total_sql, [])
        total_count = cursor.fetchone()
        
        conn.close()
        
        return {
            "items": self._task_to_dict(task) for task in tasks
        }, len(tasks), 1, 10
    
    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        
        if row:
            conn.close()
            return self._task_to_dict(row)
        return None
    
    def update_task(self, task_id: int,
                    title: Optional[str] = None,
                    description: Optional[str] = None,
                    completed: Optional[bool] = None,
                    priority: Optional[str] = None) -> bool:
        """Update a task."""
        values = []
        params = []
        
        if title is not None:
            values.append("title = ?")
            params.append(title)
        if description is not None:
            values.append("description = ?")
            params.append(description)
        if completed is not None:
            values.append("completed = ?")
            params.append(completed)
        if priority is not None:
            values.append("priority = ?")
            params.append(priority)
        
        if not values:
            return True
        
        sql = "UPDATE tasks SET " + ", ".join(values) + " WHERE id = ?"
        params.append(task_id)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0
    
    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    
    def _task_to_dict(self, row):
        """Convert database row to Task model."""
        return Task(
            id=row[0],
            title=row[1],
            description=row[2],
            completed=bool(row[3]),
            priority=row[4],
            created_at=row[5]
        )


# Initialize database and app on startup
db = TaskDatabase()

# Validate priority values
VALID_PRIORITIES = {"low", "medium", "high"}

# Create the app
fastapi_app = FastAPI()

# Add dependencies for the app
# For importability as main.app, we'll use fastapi_app directly

# Helper functions
def validate_title(title: str) -> None:
    """Validate title field."""
    title = title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required")
    if len(title) > 200:
        raise HTTPException(status_code=422, detail="Title must be 1-200 characters")

def validate_priority(priority: str) -> None:
    """Validate priority field."""
    if priority not in VALID_PRIORITIES:
        raise HTTPException(status_code=422, detail="Priority must be low, medium, or high")

# Endpoints

@fastapi_app.post("/tasks")
def create_task(task: TaskModel):
    """Create a new task."""
    validate_title(task.title)
    
    priority = task.priority if task.priority else "medium"
    validate_priority(priority)
    
    completed = task.completed if task.completed is not None else False
    
    task_id, task = db.create_task(
        title=task.title,
        description=task.description,
        priority=priority,
        completed=completed
    )
    
    return task

@fastapi_app.get("/tasks")
def list_tasks(completed: Optional[bool] = None,
               priority: Optional[str] = None,
               page: int = 1,
               page_size: int = 10):
    """List tasks with pagination."""
    # Validate page
    if page < 1:
        raise HTTPException(status_code=422, detail="page must be >= 1")
    
    # Validate page_size
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=422, detail="page_size must be 1-100")
    
    # Validate priority
    if priority is not None:
        validate_priority(priority)
    
    tasks = db.get_tasks(
        completed=completed,
        priority=priority,
        page=page,
        page_size=page_size
    )
    
    return {
        "items": tasks["items"],
        "total": tasks["total"],
        "page": tasks["page"],
        "page_size": tasks["page_size"]
    }

@fastapi_app.get("/tasks/{task_id}")
def get_task(task_id: int):
    """Get a task by ID."""
    task = db.get_task(task_id)
    
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return task

@fastapi_app.put("/tasks/{task_id}")
def update_task(task_id: int,
                title: Optional[str] = None,
                description: Optional[str] = None,
                completed: Optional[bool] = None,
                priority: Optional[str] = None):
    """Update a task."""
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    validate_title(title)
    if priority is not None:
        validate_priority(priority)
    
    # Update the task
    success = db.update_task(
        task_id=task_id,
        title=title,
        description=description,
        completed=completed,
        priority=priority
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get updated task
    task = db.get_task(task_id)
    return task

@fastapi_app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    """Delete a task."""
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    
    success = db.delete_task(task_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return ""


# Create task response for partial update
class TaskUpdate(BaseModel):
    """Model for task update response."""
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str


# Override TaskModel to support partial updates
class TaskRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = None


@fastapi_app.put("/tasks/{task_id}")
def update_task(task_id: int, task: TaskRequest):
    """Partial update task."""
    validate_title(task.title)
    
    priority = task.priority if task.priority is not None else None
    if priority is not None:
        validate_priority(priority)
    
    completed = task.completed if task.completed is not None else None
    
    success = db.update_task(
        task_id=task_id,
        title=task.title,
        description=task.description,
        completed=completed,
        priority=priority
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return db.get_task(task_id)
```

```python
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    created_at: str

class TaskResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

VALID_PRIORITIES = {"low", "medium", "high"}

db = sqlite3.connect("tasks.db")
cursor = db.cursor()

def init_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    db.commit()
    cursor.close()
    db.close()

init_db()

def get_task(task_id):
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    return None

def create_task(title, description=None, priority="medium", completed=False):
    cursor.execute('''
        INSERT INTO tasks (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, description, 1 if completed else 0, priority, datetime.now().isoformat()))
    task_id = cursor.lastrowid
    cursor.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.close()
    cursor = db.cursor()
    
def list_tasks(completed=None, priority=None, page=1, page_size=10):
    sql = "SELECT * FROM tasks ORDER BY id ASC"
    params = []
    if completed is not None:
        sql += " WHERE completed = ?"
        params.append(completed)
    if priority is not None:
        sql += " AND priority = ?"
        params.append(priority)
    
    cursor.execute(sql, params)
    tasks = cursor.fetchall()
    total = len(tasks)
    return {"items": [dict(r) for r in tasks], "total": total, "page": page, "page_size": page_size}

def get_one(task_id):
    row = get_task(task_id)
    if row:
        return row
    raise HTTPException(status_code=404, detail="Task not found")

def update_one(task_id, **kwargs):
    row = get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    cursor.execute("UPDATE tasks SET title = ?, description = ?, completed = ?, priority = ? WHERE id = ?",
                  (kwargs.get("title"), kwargs.get("description"), 
                   1 if kwargs.get("completed") else 0, kwargs.get("priority"), task_id))
    
    db.commit()
    
    return get_task(task_id)

def delete_one(task_id):
    get_task(task_id)
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
```

```python
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import sys
import os

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    created_at: str

class TaskResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

VALID_PRIORITIES = {"low", "medium", "high"}
db_path = "tasks.db"

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_task(task_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    conn.close()
    return None

def create_task(title, description=None, priority="medium", completed=False):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, description, 1 if completed else 0, priority, datetime.now().isoformat()))
    task_id = cursor.lastrowid
    cursor.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "completed": row[3],
        "priority": row[4],
        "created_at": row[5]
    }

def list_tasks(completed=None, priority=None, page=1, page_size=10):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    sql = "SELECT * FROM tasks ORDER BY id ASC"
    params = []
    if completed is not None:
        sql += " WHERE completed = ?"
        params.append(completed)
    if priority is not None:
        sql += " AND priority = ?"
        params.append(priority)
    
    cursor.execute(sql, params)
    tasks = [dict(row) for row in cursor.fetchall()]
    total = len(tasks)
    conn.close()
    return {"items": tasks, "total": total, "page": page, "page_size": page_size}

def get_one(task_id):
    row = get_task(task_id)
    if row:
        return row
    raise HTTPException(status_code=404, detail="Task not found")

def update_one(task_id, title=None, description=None, completed=None, priority=None):
    row = get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    values = []
    if title is not None:
        values.append("title = ?")
        params.append(title)
    if description is not None:
        values.append("description = ?")
        params.append(description)
    if completed is not None:
        values.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        values.append("priority = ?")
        params.append(priority)
    
    if values:
        sql = "UPDATE tasks SET " + ", ".join(values) + " WHERE id = ?"
        params.append(task_id)
        cursor.execute(sql, params)
    conn.commit()
    return get_task(task_id)

def delete_one(task_id):
    get_task(task_id)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
```

```python
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Optional, List, Tuple
import sys
import os

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    created_at: str

class TaskResponse(BaseModel):
    items: List[dict]
    total: int
    page: int
    page_size: int

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

VALID_PRIORITIES = {"low", "medium", "high"}
db_path = "tasks.db"

def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed INTEGER NOT NULL DEFAULT 0,
            priority TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_task(task_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    if row:
        return dict(row)
    conn.close()
    return None

def create_task(title, description=None, priority="medium", completed=False):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, description, 1 if completed else 0, priority, datetime.now().isoformat()))
    task_id = cursor.lastrowid
    cursor.execute(
        "SELECT id, title, description, completed, priority, created_at FROM tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "completed": row[3],
        "priority": row[4],
        "created_at": row[5]
    }

def list_tasks(completed=None, priority=None, page=1, page_size=10):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    sql = "SELECT * FROM tasks ORDER BY id ASC"
    params = []
    if completed is not None:
        sql += " WHERE completed = ?"
        params.append(completed)
    if priority is not None:
        sql += " AND priority = ?"
        params.append(priority)
    
    cursor.execute(sql, params)
    tasks = [dict(row) for row in cursor.fetchall()]
    total = len(tasks)
    conn.close()
    return {"items": tasks, "total": total, "page": page, "page_size": page_size}

def get_one(task_id):
    row = get_task(task_id)
    if row:
        return row
    raise HTTPException(status_code=404, detail="Task not found")

def update_one(task_id, title=None, description=None, completed=None, priority=None):
    row = get_task(task_id)
    if not row:
        raise HTTPException(status_code=404, detail="Task not found")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    values = []
    if title is not None:
        values.append("title = ?")
        params.append(title)
    if description is not None:
        values.append("description = ?")
        params.append(description)
    if completed is not None:
        values.append("completed = ?")
        params.append(1 if completed else 0)
    if priority is not None:
        values.append("priority = ?")
        params.append(priority)
    
    if values:
        sql = "UPDATE tasks SET " + ", ".join(values) + " WHERE id = ?"
        params.append(task_id)
        cursor.execute(sql, params)
    conn.commit()
    return get_task(task_id)

def delete_one(task_id):
    get_task(task_id)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
```