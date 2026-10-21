```python
import os
import sqlite3
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, field_validator

# Initialize FastAPI app
app = FastAPI()

# Database connection
def get_db():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')
    conn = sqlite3.connect(db_path)
    conn.execute('CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL CHECK (title NOT EMPTY),
        description TEXT,
        completed BOOLEAN DEFAULT FALSE,
        priority TEXT DEFAULT 'medium',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )')
    return conn

# Task model
class TaskCreateBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None

def validate_priority(priority: str) -> str:
    allowed_values = ['low', 'medium', 'high']
    if priority not in allowed_values:
        raise HTTPException(status_code=422, detail="Priority must be one of: low, medium, high")
    return priority

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = 'medium'
    created_at: datetime = None

# Create task endpoint
@app.post("/tasks")
async def create_task(request: TaskCreateBase):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO tasks VALUES (?, ?, ?, ?, ?)',
            (request.title, request.description, request.priority, request.id)
        )
        conn.commit()
        task = Task(id=request.id, title=request.title, description=request.description,
                     priority=request.priority, created_at=datetime.now())
        conn.close()
        return task
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        conn.close()

# GET /tasks
async def get_tasks(page: int = Query(default=1, ge=1),
                   page_size: int = Query(default=10, le=100),
                   completed: Optional[bool] = None,
                   priority: Optional[str] = None):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks")
        cursor.execute('SELECT COUNT(*) FROM tasks')
        cursor.execute(f'SELECT * FROM tasks WHERE completed = {completed is not None}')
        results = cursor.fetchall()
        
        total = cursor.fetchone()[0] if cursor.fetchone() else 0
        current_total = cursor.fetchone()[0] if cursor.fetchone() else 0
        
        # Query logic
        query = """
            SELECT t.* FROM tasks t
            WHERE t.id BETWEEN ? AND ?
            ORDER BY t.id ASC
            LIMIT ? OFFSET ?
        """
        params = [page + 1, total + 1, page_size, page]
        
        cursor.execute(query, params)
        items = cursor.fetchall()
        
        conn.close()
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))

# GET /tasks/{id}
async def get_task(id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks WHERE id = ?', (id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return row
        raise HTTPException(status_code=404, detail="Task not found")
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=str(e))

# PUT /tasks/{id}
async def update_task(id: int, request: TaskCreateBase):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tasks SET title=?, description=?, completed=?, priority=? WHERE id = ?',
            (request.title, request.description, request.completed, request.priority, id)
        )
        conn.commit()
        task = Task(id=id, title=request.title, description=request.description,
                     priority=request.priority, created_at=datetime.now())
        conn.close()
        return task
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    finally:
        conn.close()

# DELETE /tasks/{id}
async def delete_task(id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE id = ?', (id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(status_code=404, detail="Task not found")
    finally:
        conn.close()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```