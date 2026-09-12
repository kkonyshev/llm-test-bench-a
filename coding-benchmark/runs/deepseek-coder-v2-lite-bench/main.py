from fastapi import FastAPI, HTTPException, Query, Path, Body
from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
import sqlite3
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Table, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = FastAPI()

# Database setup
DATABASE_URL = "sqlite:///./tasks.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Task model
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(String, default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Pydantic models
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"

    @validator('title')
    def validate_title(cls, v):
        if not v:
            raise ValueError('Title must be non-empty')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of low, medium, high')
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator('title')
    def validate_title(cls, v):
        if v is not None and not v:
            raise ValueError('Title must be non-empty')
        return v

    @validator('priority')
    def validate_priority(cls, v):
        if v is not None and v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of low, medium, high')
        return v

# Routes
@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate):
    db = SessionLocal()
    db_task = Task(**task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/tasks", response_model=dict)
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100)
):
    db = SessionLocal()
    query = db.query(Task)

    if completed is not None:
        query = query.filter(Task.completed == completed)

    if priority is not None:
        if priority not in ['low', 'medium', 'high']:
            raise HTTPException(status_code=422, detail="Invalid priority value")
        query = query.filter(Task.priority == priority)

    total = query.count()
    tasks = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": tasks,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}", response_model=Task)
def get_task(id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.put("/tasks/{id}", response_model=Task)
def update_task(id: int, task: TaskUpdate):
    db = SessionLocal()
    db_task = db.query(Task).filter(Task.id == id).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    for field, value in task.dict().items():
        if value is not None:
            setattr(db_task, field, value)

    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int):
    db = SessionLocal()
    task = db.query(Task).filter(Task.id == id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return
