from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import sqlite3
from sqlite3 import Error

app = FastAPI()

class Task(BaseModel):
    id: Optional[int]
    title: str
    description: Optional[str]
    completed: Optional[bool] = False
    priority: Optional[str] = "medium"
    created_at: Optional[str]

    @validator("title")
    def title_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Title must not be empty")
        return v

    @validator("priority")
    def priority_must_be_valid(cls, v):
        if v not in ["low", "medium", "high"]:
            raise ValueError("Priority must be one of 'low', 'medium', 'high'")
        return v

class TaskListResponse(BaseModel):
    items: List[Task]
    total: int
    page: int
    page_size: int

def create_connection():
    conn = None
    try:
        conn = sqlite3.connect("tasks.db")
        print(sqlite3.version)
    except Error as e:
        print(e)
    return conn

def create_table(conn):
    sql = """ CREATE TABLE IF NOT EXISTS tasks (
                                        id integer PRIMARY KEY AUTOINCREMENT,
                                        title text NOT NULL,
                                        description text,
                                        completed integer,
                                        priority text,
                                        created_at text
                                    ); """
    try:
        c = conn.cursor()
        c.execute(sql)
    except Error as e:
        print(e)

def create_task(conn, task):
    sql = """ INSERT INTO tasks(title,description,completed,priority,created_at)
              VALUES(?,?,?,?,?) """
    try:
        c = conn.cursor()
        c.execute(sql, (task.title, task.description, task.completed, task.priority, task.created_at))
        conn.commit()
        return c.lastrowid
    except Error as e:
        print(e)

def get_all_tasks(conn, completed=None, priority=None, page=1, page_size=10):
    sql = """ SELECT * FROM tasks """
    conditions = []
    params = []
    if completed is not None:
        conditions.append("completed = ?")
        params.append(completed)
    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY id ASC LIMIT ? OFFSET ?"
    params.extend([page_size, (page - 1) * page_size])
    try:
        c = conn.cursor()
        c.execute(sql, params)
        rows = c.fetchall()
        return rows
    except Error as e:
        print(e)

def get_task(conn, id):
    sql = """ SELECT * FROM tasks WHERE id = ? """
    try:
        c = conn.cursor()
        c.execute(sql, (id,))
        row = c.fetchone()
        return row
    except Error as e:
        print(e)

def update_task(conn, id, task):
    sql = """ UPDATE tasks SET title = ?, description = ?, completed = ?, priority = ? WHERE id = ? """
    try:
        c = conn.cursor()
        c.execute(sql, (task.title, task.description, task.completed, task.priority, id))
        conn.commit()
    except Error as e:
        print(e)

def delete_task(conn, id):
    sql = """ DELETE FROM tasks WHERE id = ? """
    try:
        c = conn.cursor()
        c.execute(sql, (id,))
        conn.commit()
    except Error as e:
        print(e)

@app.on_event("startup")
def startup_event():
    conn = create_connection()
    create_table(conn)
    conn.close()

@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task_endpoint(task: Task):
    conn = create_connection()
    task.created_at = datetime.now().isoformat()
    task_id = create_task(conn, task)
    task.id = task_id
    conn.close()
    return task

@app.get("/tasks", response_model=TaskListResponse)
def get_all_tasks_endpoint(completed: Optional[bool] = None, priority: Optional[str] = None, page: int = 1, page_size: int = 10):
    if page < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Page must be greater than 0")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Page size must be between 1 and 100")
    if priority is not None and priority not in ["low", "medium", "high"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Priority must be one of 'low', 'medium', 'high'")
    conn = create_connection()
    tasks = get_all_tasks(conn, completed, priority, page, page_size)
    total_tasks = len(get_all_tasks(conn, completed, priority))
    task_list = []
    for task in tasks:
        task_list.append(Task(id=task[0], title=task[1], description=task[2], completed=task[3], priority=task[4], created_at=task[5]))
    conn.close()
    return TaskListResponse(items=task_list, total=total_tasks, page=page, page_size=page_size)

@app.get("/tasks/{id}", response_model=Task)
def get_task_endpoint(id: int):
    conn = create_connection()
    task = get_task(conn, id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    conn.close()
    return Task(id=task[0], title=task[1], description=task[2], completed=task[3], priority=task[4], created_at=task[5])

@app.put("/tasks/{id}", response_model=Task)
def update_task_endpoint(id: int, task: Task):
    conn = create_connection()
    existing_task = get_task(conn, id)
    if existing_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    updated_task = Task(id=id, title=task.title if task.title else existing_task[1], description=task.description if task.description else existing_task[2], completed=task.completed if task.completed is not None else existing_task[3], priority=task.priority if task.priority else existing_task[4], created_at=existing_task[5])
    update_task(conn, id, updated_task)
    conn.close()
    return updated_task

@app.delete("/tasks/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_endpoint(id: int):
    conn = create_connection()
    task = get_task(conn, id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    delete_task(conn, id)
    conn.close()
    return JSONResponse(content={}, status_code=status.HTTP_204_NO_CONTENT)
