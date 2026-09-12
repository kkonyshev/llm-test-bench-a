from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, validator
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import List, Optional

# Initialize FastAPI app
app = FastAPI()

# Initialize SQLite database
SQLALCHEMY_DATABASE_URL = "sqlite:///tasks.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize SQLAlchemy base model
Base = declarative_base()

# Define Task model for SQLAlchemy
class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(Enum("low", "medium", "high", name="priority"), default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)

# Create all tables in the engine
Base.metadata.create_all(engine)

# Define Task model for Pydantic (API request/response validation)
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"

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

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @validator("title")
    def title_must_not_be_empty_if_provided(cls, v):
        if v is not None and not v.strip():
            raise ValueError("Title must not be empty")
        return v

    @validator("priority")
    def priority_must_be_valid_if_provided(cls, v):
        if v is not None and v not in ["low", "medium", "high"]:
            raise ValueError("Priority must be one of 'low', 'medium', 'high'")
        return v

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: datetime

    class Config:
        orm_mode = True

# Define pagination response model
class PaginatedTasks(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int

# Dependency to get a database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate, db = Depends(get_db)):
    db_task = Task(title=task.title, description=task.description, priority=task.priority)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/tasks", response_model=PaginatedTasks)
def read_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    db = Depends(get_db)
):
    query = db.query(Task)
    if completed is not None:
        query = query.filter(Task.completed == completed)
    if priority is not None:
        if priority not in ["low", "medium", "high"]:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid priority")
        query = query.filter(Task.priority == priority)
    if page < 1:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Page must be >= 1")
    if page_size < 1 or page_size > 100:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Page size must be between 1 and 100")
    total = query.count()
    query = query.offset((page - 1) * page_size).limit(page_size)
    tasks = query.all()
    return {"items": tasks, "total": total, "page": page, "page_size": page_size}

@app.get("/tasks/{id}", response_model=TaskResponse)
def read_task(id: int, db = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task

@app.put("/tasks/{id}", response_model=TaskResponse)
def update_task(id: int, task: TaskUpdate, db = Depends(get_db)):
    db_task = db.query(Task).filter(Task.id == id).first()
    if db_task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    update_data = task.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.delete("/tasks/{id}")
def delete_task(id: int, db = Depends(get_db)):
    task = db.query(Task).filter(Task.id == id).first()
    if task is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"detail": "Task deleted"}
