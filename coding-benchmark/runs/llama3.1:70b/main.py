from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.requests import Request
from fastapi.responses import Response
from pydantic import BaseModel, validator
from typing import Optional, List
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import json

app = FastAPI()

# Connect to SQLite database. It will be created if it doesn't exist.
engine = create_engine('sqlite:///tasks.db')
Base = declarative_base()

class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, nullable=False, default=False)
    priority = Column(String, nullable=False, default='medium')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

Base.metadata.create_all(engine)

# Create a session maker
Session = sessionmaker(bind=engine)

class TaskModel(BaseModel):
    title: str
    description: Optional[str]
    priority: str = 'medium'

    @validator('priority')
    def priority_must_be_valid(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('Priority must be one of low, medium, high')
        return v

    @validator('title')
    def title_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError('Title must not be empty')
        return v

class TaskFullModel(TaskModel):
    id: int
    completed: bool
    created_at: datetime

    class Config:
        orm_mode = True

class PaginatedTasksModel(BaseModel):
    items: List[TaskFullModel]
    total: int
    page: int
    page_size: int

# Dependency to get a database session
def get_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()

@app.post('/tasks', status_code=status.HTTP_201_CREATED, response_model=TaskFullModel)
async def create_task(task: TaskModel, db: Session = Depends(get_db)):
    new_task = Task(title=task.title, description=task.description, priority=task.priority)
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task

@app.get('/tasks', response_model=PaginatedTasksModel)
async def get_tasks(completed: Optional[bool] = None, priority: Optional[str] = None,
                    page: int = 1, page_size: int = 10, db: Session = Depends(get_db)):
    query = db.query(Task)
    if completed is not None:
        query = query.filter(Task.completed == completed)
    if priority is not None:
        if priority not in ['low', 'medium', 'high']:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Priority must be one of low, medium, high')
        query = query.filter(Task.priority == priority)
    total = query.count()
    query = query.offset((page - 1) * page_size).limit(page_size).order_by(Task.id)
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Page and page_size must be valid')
    return {
        'items': query.all(),
        'total': total,
        'page': page,
        'page_size': page_size
    }

@app.get('/tasks/{task_id}', response_model=TaskFullModel)
async def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found')
    return task

@app.put('/tasks/{task_id}', response_model=TaskFullModel)
async def update_task(task_id: int, task: TaskModel, db: Session = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == task_id).first()
    if db_task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found')
    db_task.title = task.title or db_task.title
    db_task.description = task.description or db_task.description
    db_task.completed = task.dict().get('completed', db_task.completed)
    db_task.priority = task.priority or db_task.priority
    db.commit()
    return db_task

@app.delete('/tasks/{task_id}')
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Task not found')
    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
