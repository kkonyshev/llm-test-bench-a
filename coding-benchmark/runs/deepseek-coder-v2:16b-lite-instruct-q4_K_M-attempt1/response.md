 ```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator
from datetime import datetime
import sqlite3
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = FastAPI()

DATABASE_URL = "sqlite:///tasks.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, index=True)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(Enum('low', 'medium', 'high', name='priority_enum'), default='medium')
    created_at = Column(DateTime, default=datetime.now)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class TaskCreate(BaseModel):
    title: str
    description: str = None
    priority: str = 'medium'

    @validator('title')
    def check_title(cls, v):
        if not v:
            raise ValueError('Title must not be empty')
        return v

    @validator('priority')
    def check_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of low, medium, high')
        return v

@app.post("/tasks", status_code=201)
def create_task(task: TaskCreate, db=Depends(get_db)):
    db_task = Task(**task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/tasks")
def list_tasks(completed: bool = None, priority: str = None, page: int = 1, page_size: int = 10, db=Depends(get_db)):
    query = db.query(Task)
    if completed is not None:
        query = query.filter(Task.completed == completed)
    if priority is not None:
        if priority not in ['low', 'medium', 'high']:
            raise HTTPException(status_code=422, detail="Invalid priority value")
        query = query.filter(Task.priority == priority)
    total = query.count()
    tasks = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": tasks, "total": total, "page": page, "page_size": page_size}

@app.get("/tasks/{id}", status_code=200)
def get_task(id: int, db=Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.put("/tasks/{id}", status_code=200)
def update_task(id: int, task: TaskCreate, db=Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == id).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = task.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/tasks/{id}", status_code=204)
def delete_task(id: int, db=Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == id).first()
    if db_task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    return None
```