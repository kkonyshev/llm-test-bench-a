```python
from fastapi import FastAPI, HTTPException, Query, status
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm import joinedload
from sqlalchemy import func
import os
import re
from datetime import datetime
from pydantic import BaseModel, field_validator, ValidationError
from typing import Optional, List

# Configuration
DB_FILE = "tasks.db"
# Using SQLAlchemy as allowed by spec
engine = create_engine(f"sqlite:///{DB_FILE}")
Base = declarative_base()

# Database Model
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(String(20), default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return self.__dict__

# Pydantic Models
class TaskBase(Base):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    created_at: str

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Title cannot be empty")
        if len(trimmed) > 200:
            raise ValueError("Title must be 1-200 characters")
        return trimmed

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid_values = ["low", "medium", "high"]
        if v is not None:
            if v not in valid_values:
                raise ValueError("Priority must be 'low', 'medium', or 'high'")
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Title cannot be empty")
            if len(trimmed) > 200:
                raise ValueError("Title must be 1-200 characters")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_values = ["low", "medium", "high"]
            if v not in valid_values:
                raise ValueError("Priority must be 'low', 'medium', or 'high'")
        return v

class TaskResponse(TaskBase):
    pass

class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int

# Create table on startup
def init_db():
    Base.metadata.create_all(engine)

# Application
app = FastAPI(title="Task Tracker API")

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(default=1, ge=1, alias="page"),
    page_size: int = Query(default=10, ge=1, le=100, alias="page_size")
):
    # Validate page_size again in case of edge cases
    if not 1 <= page_size <= 100:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 100")
    
    # Get filters
    filters = {}
    
    # Build query
    if completed is not None:
        filters["completed"] = completed
    if priority is not None:
        filters["priority"] = priority
        
    # Get total count
    # Using raw SQL for counting logic to ensure efficiency, or Session query
    if filters:
        query = session.query(Task).filter_by(**filters)
    else:
        query = session.query(Task)
    
    total_count = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    
    return {
        "items": [item.to_dict() for item in items],
        "total": total_count,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}")
def get_task(id: int):
    session = Session(engine)
    try:
        task = session.query(Task).get(id)
        if task is None:
            raise HTTPException(status_code=404)
        return task.to_dict()
    finally:
        session.close()

@app.put("/tasks/{id}")
def update_task(id: int, task_data: TaskUpdate = None):
    session = Session(engine)
    try:
        task = session.query(Task).get(id)
        if task is None:
            raise HTTPException(status_code=404)
            
        if task_data.title is not None:
            task.title = task_data.title
        if task_data.description is not None:
            task.description = task_data.description
        if task_data.completed is not None:
            task.completed = task_data.completed
        if task_data.priority is not None:
            task.priority = task_data.priority
            
        session.add(task)
        session.commit()
        return task.to_dict()
    finally:
        session.close()

@app.delete("/tasks/{id}")
def delete_task(id: int):
    session = Session(engine)
    try:
        task = session.query(Task).get(id)
        if task is None:
            raise HTTPException(status_code=404)
        session.delete(task)
        session.commit()
        return {}
    finally:
        session.close()

# Ensure app is accessible
```
</think>

```python
from fastapi import FastAPI, HTTPException, Query, status
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, field_validator, ValidationError
from sqlalchemy.orm import joinedload
import re
import sys

# Configuration
DB_FILE = "tasks.db"
# Using SQLAlchemy as allowed by spec
engine = create_engine(f"sqlite:///{DB_FILE}")
Base = declarative_base()

# Database Model
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(String(20), default="medium")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

# Pydantic Models
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: Optional[str] = "medium"

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Title cannot be empty")
        if len(trimmed) > 200:
            raise ValueError("Title must be 1-200 characters")
        return trimmed

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        valid_values = ["low", "medium", "high"]
        if v is not None:
            if v not in valid_values:
                raise ValueError("Priority must be 'low', 'medium', or 'high'")
        return v

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            trimmed = v.strip()
            if not trimmed:
                raise ValueError("Title cannot be empty")
            if len(trimmed) > 200:
                raise ValueError("Title must be 1-200 characters")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_values = ["low", "medium", "high"]
            if v not in valid_values:
                raise ValueError("Priority must be 'low', 'medium', or 'high'")
        return v

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    completed: bool = False
    priority: str = "medium"
    created_at: str

class TaskListResponse(BaseModel):
    items: List[TaskResponse]
    total: int
    page: int
    page_size: int

# Application
app = FastAPI(title="Task Tracker API")

@app.on_event("startup")
def startup_event():
    Base.metadata.create_all(engine)

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(default=1, ge=1, alias="page"),
    page_size: int = Query(default=10, ge=1, le=100, alias="page_size")
):
    # Validate page_size again to ensure constraints
    if not 1 <= page_size <= 100:
        raise HTTPException(status_code=422, detail="page_size must be between 1 and 100")
    
    # Build filters
    filters = {}
    
    # Count tasks
    if completed is not None:
        filters["completed"] = completed
    if priority is not None:
        filters["priority"] = priority
        
    query = session.query(Task).filter_by(**filters) if filters else session.query(Task)
    total_count = query.count()
    
    # Pagination
    offset = (page - 1) * page_size
    items = query.offset(offset).limit(page_size).all()
    
    return {
        "items": [item.to_dict() for item in items],
        "total": total_count,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}")
def get_task(id: int):
    try:
        session = Session(engine)
        task = session.query(Task).get(id)
        if task is None:
            raise HTTPException(status_code=404)
        return task.to_dict()
    finally:
        session.close()

@app.put("/tasks/{id}")
def update_task(id: int, task_data: TaskUpdate = None):
    try:
        session = Session(engine)
        task = session.query(Task).get(id)
        if task is None:
            raise HTTPException(status_code=404)
            
        if task_data.title is not None:
            task.title = task_data.title
        if task_data.description is not None:
            task.description = task_data.description
        if task_data.completed is not None:
            task.completed = task_data.completed
        if task_data.priority is not None:
            task.priority = task_data.priority
            
        session.commit()
        return task.to_dict()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

@app.delete("/tasks/{id}")
def delete_task(id: int):
    try:
        session = Session(engine)
        task = session.query(Task).get(id)
        if task is None:
            raise HTTPException(status_code=404)
        session.delete(task)
        session.commit()
        return {}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Export app for importability
main = __import__(__name__)
main.app = app
```