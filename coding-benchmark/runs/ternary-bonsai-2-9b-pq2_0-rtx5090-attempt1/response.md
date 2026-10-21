```python
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Optional, Any

import fastapi
from pydantic import BaseModel, Field
from sqlalchemy import create_async_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session, declarative_base
import os

# Database Configuration
DATABASE_URL = "sqlite:///./tasks.db"
engine = create_async_engine(DATABASE_URL, echo=False)
Base = declarative_base()

# Models
class TaskBase(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(String(10), default="medium")
    created_at = Column(DateTime(timezone=True))

# Task Pydantic Models
class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool
    priority: str
    created_at: str

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = Field(default="medium")

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

# Database Setup
async_sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
SessionLocal = async_sessionmaker

# Endpoints and Logic
VALID_PRIORITY = {"low", "medium", "high"}

async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/tasks", response_model=TaskResponse)
async def create_task(db: Session = Depends(get_db), task: TaskCreate = None):
    if not task.title.strip():
        raise fastapi.HTTPException(status_code=422, detail="Title is required and cannot be empty")
    
    # Validate priority
    priority_to_use = task.priority if task.priority else "medium"
    if priority_to_use not in VALID_PRIORITY:
        raise fastapi.HTTPException(status_code=422, detail="Priority must be low, medium, or high")
    
    # Trim title for validation length
    title_to_use = task.title.strip()
    if len(title_to_use) > 200:
        raise fastapi.HTTPException(status_code=422, detail="Title must be between 1 and 200 characters")

    async def create_task_in_db():
        db.add(TaskBase(title=title_to_use, description=task.description, priority=priority_to_use))
        await db.commit()
        await db.refresh(task)
        # Update title in model to strip version
        task.title = title_to_use
        return task

    result = await create_task_in_db()
    return result

@app.get("/tasks", response_model=Dict[str, Any])
async def list_tasks(
    db: Session = Depends(get_db),
    completed: Optional[bool] = None,
    priority: Optional[str] = None,
    page: int = 1,
    page_size: int = 10
):
    # Validate pagination
    if page < 1:
        raise fastapi.HTTPException(status_code=422, detail="Page must be >= 1")
    if not (1 <= page_size <= 100):
        raise fastapi.HTTPException(status_code=422, detail="Page size must be between 1 and 100")

    # Validation for priority filter
    if priority and priority not in VALID_PRIORITY:
        raise fastapi.HTTPException(status_code=422, detail="Priority filter must be low, medium, or high")

    query = db.query(TaskBase)
    
    # Filter logic
    if completed is not None:
        query = query.filter(TaskBase.completed == completed)
    if priority is not None:
        query = query.filter(TaskBase.priority == priority)
    
    # Get total count for pagination
    total_count = query.count()
    
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Paginate
    items = query.offset(offset).limit(page_size).all()
    
    return {
        "items": [t.dict() for t in items],
        "total": total_count,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}", response_model=TaskResponse)
async def get_task(db: Session = Depends(get_db), task_id: int = ...):
    task = db.query(TaskBase).filter(TaskBase.id == task_id).first()
    if not task:
        raise fastapi.HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        completed=task.completed,
        priority=task.priority,
        created_at=task.created_at.isoformat()
    )

@app.put("/tasks/{id}", response_model=TaskResponse)
async def update_task(
    db: Session = Depends(get_db),
    task_id: int = ...,
    task_update: TaskUpdate = None
):
    # Validate provided fields if any exist
    # Note: FastAPI might not trigger field validation if field is None/omitted unless configured
    # We'll check logic manually or rely on Pydantic if we ensure non-None validation
    if task_update:
        # Check priority if provided
        if task_update.priority is not None:
            if task_update.priority not in VALID_PRIORITY:
                raise fastapi.HTTPException(status_code=422, detail="Priority must be low, medium, or high")
        # Check title if provided
        if task_update.title is not None:
            if not task_update.title.strip():
                raise fastapi.HTTPException(status_code=422, detail="Title is required and cannot be empty")
            if len(task_update.title.strip()) > 200:
                raise fastapi.HTTPException(status_code=422, detail="Title must be between 1 and 200 characters")

    task = db.query(TaskBase).filter(TaskBase.id == task_id).first()
    if not task:
        raise fastapi.HTTPException(status_code=404, detail="Task not found")

    # Apply updates
    if task_update.title is not None:
        task.title = task_update.title.strip()
    if task_update.description is not None:
        task.description = task_update.description
    if task_update.completed is not None:
        task.completed = task_update.completed
    if task_update.priority is not None:
        task.priority = task_update.priority

    await db.commit()
    await db.refresh(task)
    
    return TaskResponse(
        id=task.id,
        title=task.title,
        description=task.description,
        completed=task.completed,
        priority=task.priority,
        created_at=task.created_at.isoformat()
    )

@app.delete("/tasks/{id}", status_code=204)
async def delete_task(db: Session = Depends(get_db), task_id: int = ...):
    task = db.query(TaskBase).filter(TaskBase.id == task_id).first()
    if not task:
        raise fastapi.HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()

# Startup
@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
```