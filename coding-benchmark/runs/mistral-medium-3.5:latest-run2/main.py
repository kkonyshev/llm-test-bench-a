from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlite3 import connect, Row

app = FastAPI(title="Task Tracker API")

PRIORITIES = {"low", "medium", "high"}

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = "medium"

    @validator("priority")
    def priority_must_be_valid(cls, v):
        if v and v.lower() not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        return v.lower() if v else "medium"

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator("priority")
    def priority_must_be_valid(cls, v):
        if v and v.lower() not in PRIORITIES:
            raise ValueError(f"priority must be one of {PRIORITIES}")
        return v.lower() if v else None

class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    completed: bool
    priority: str
    created_at: str

def get_db():
    conn = connect("tasks.db", check_same_thread=False)
    conn.row_factory = Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            completed BOOLEAN NOT NULL DEFAULT 0,
            priority TEXT NOT NULL DEFAULT 'medium',
            created_at TEXT NOT NULL
        )
        """
    )
    return conn

@app.on_event("startup")
def on_startup():
    get_db()

def row_to_task(row: Row) -> TaskOut:
    return TaskOut(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        completed=bool(row["completed"]),
        priority=row["priority"],
        created_at=row["created_at"],
    )

@app.post("/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    db = get_db()
    now = datetime.utcnow().isoformat()
    cursor = db.execute(
        """
        INSERT INTO tasks (title, description, completed, priority, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            task.title.strip(),
            task.description,
            False,
            task.priority,
            now,
        ),
    )
    db.commit()
    task_id = cursor.lastrowid
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    db.close()
    return row_to_task(row)

@app.get("/tasks", response_model=dict)
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    if priority and priority.lower() not in PRIORITIES:
        raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")

    db = get_db()
    query = "SELECT COUNT(*) FROM tasks WHERE 1=1"
    params: List = []
    if completed is not None:
        query += " AND completed = ?"
        params.append(int(completed))
    if priority:
        query += " AND priority = ?"
        params.append(priority.lower())
    total = db.execute(query, tuple(params)).fetchone()[0]

    query = "SELECT * FROM tasks WHERE 1=1"
    if completed is not None:
        query += " AND completed = ?"
        params.append(int(completed))
    if priority:
        query += " AND priority = ?"
        params.append(priority.lower())
    query += " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    rows = db.execute(query, tuple(params)).fetchall()
    db.close()

    return {
        "items": [row_to_task(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@app.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    db.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return row_to_task(row)

@app.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, task: TaskUpdate):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")

    updates = []
    params: List = []
    if task.title is not None:
        updates.append("title = ?")
        params.append(task.title.strip())
    if task.description is not None:
        updates.append("description = ?")
        params.append(task.description)
    if task.completed is not None:
        updates.append("completed = ?")
        params.append(int(task.completed))
    if task.priority is not None:
        updates.append("priority = ?")
        params.append(task.priority)

    if not updates:
        db.close()
        return row_to_task(row)

    params.append(task_id)
    query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
    db.execute(query, tuple(params))
    db.commit()

    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    db.close()
    return row_to_task(row)

@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    db = get_db()
    cursor = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    if cursor.rowcount == 0:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")
    db.close()
