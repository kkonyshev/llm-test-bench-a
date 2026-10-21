import os
import sqlite3
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from fastapi import status
from pydantic import BaseModel

# Define the database path
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')

# Create database table if not exists
def create_table(db_connection):
    cursor = db_connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            completed BOOLEAN DEFAULT FALSE,
            priority VARCHAR(10) DEFAULT 'medium',
            created_at TIMESTAMP
        )
    ''')
    db_connection.commit()

# Create API router
router = APIRouter()

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = 'medium'
    
    def validate(self):
        if not self.title or not self.title.strip():
            raise HTTPException(status_code=422, detail='title is required')
        if self.priority and not self.priority in ['low', 'medium', 'high']:
            raise HTTPException(status_code=422, detail='priority must be one of low, medium, high')

class Task(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = 'medium'
    created_at: datetime = None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_db():
    try:
        conn = get_db_connection()
        create_table(conn)
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f'Database error: {e}')

# Create database on startup
create_db()

router.register(r'POST', TaskCreate)

router.get('/tasks', TaskCreate)

router.get('/tasks', TaskList)

class TaskList(BaseModel):
    page: int = 1
    page_size: int = 10
    completed: Optional[bool] = None
    priority: Optional[str] = None

router.get(r'/tasks/{id}', TaskResponse)

router.put(r'/tasks/{id}', TaskResponse)

router.delete(r'/tasks/{id}', TaskResponse)

class TaskResponse(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int

@router.get('/tasks')
def get_tasks(request: TaskList):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = """
            SELECT id, title, description, completed, priority, created_at
            FROM tasks
            WHERE ?
            ORDER BY id ASC
            LIMIT ?
        """
        params = {'completed': request.completed, 'priority': request.priority, 'page': request.page, 'page_size': request.page_size}
        cursor.execute(query, params)
        results = cursor.fetchall()
        total = len(results)
        page = request.page
        page_size = request.page_size
        items = []
        for row in results:
            tasks = Task(id=row['id'], title=row['title'], description=row['description'], completed=row['completed'], priority=row['priority'], created_at=row['created_at'])
            items.append(tasks)
        conn.close()
        return TaskResponse(items=items, total=total, page=page, page_size=page_size)
    except HTTPException:
        return {}
    except Exception as e:
        return {'error': str(e)}

@app.get('/')
def root():
    return {'status': 'OK'}
