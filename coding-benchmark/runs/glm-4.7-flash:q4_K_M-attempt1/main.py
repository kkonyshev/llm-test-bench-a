import datetime
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query, Path, Depends
from pydantic import BaseModel, Field, validator
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import Session, sessionmaker

# --- Database Setup ---
DATABASE_URL = "sqlite:///./tasks.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class TaskDB(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(String, nullable=True)
    completed = Column(Boolean, default=False)
    priority = Column(String(20), default="medium")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

# --- Pydantic Models ---
ALLOWED_PRIORITIES = ["low", "medium", "high"]

class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = Field("medium")
    completed: bool = False

    @validator('title')
    def validate_title(cls, v):
        return v.strip()

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = Field(None)
    completed: Optional[bool] = None

    @validator('priority')
    def validate_priority(cls, v):
        if v is not None and v not in ALLOWED_PRIORITIES:
            raise ValueError('Invalid priority value')
        return v

    @validator('title')
    def validate_title(cls, v):
        if v is not None:
            return v.strip()
        return None

class TaskResponse(TaskBase):
    id: int
    created_at: datetime.datetime

    class Config:
        from_attributes = True

# --- FastAPI App ---
app = FastAPI()

@app.on_event("startup")
def startup_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Endpoints ---

@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    db_task = TaskDB(**task.dict())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/tasks")
def list_tasks(
    completed: Optional[bool] = None,
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    # Validate query params
    if priority and priority not in ALLOWED_PRIORITIES:
        raise HTTPException(status_code=422, detail="Invalid priority value")

    query = db.query(TaskDB)

    if completed is not None:
        query = query.filter(TaskDB.completed == completed)
    if priority:
        query = query.filter(TaskDB.priority == priority)

    total = query.count()
    tasks = query.order_by(TaskDB.id).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "items": tasks,
        "total": total,
        "page": page,
        "page_size": page_size
    }

@app.get("/tasks/{id}", response_model=TaskResponse)
def get_task(id: int, db: Session = Depends(get_db)):
    task = db.query(TaskDB).filter(TaskDB.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.put("/tasks/{id}", response_model=TaskResponse)
def update_task(
    id: int,
    task_update: TaskUpdate,
    db: Session = Depends(get_db)
):
    task = db.query(TaskDB).filter(TaskDB.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Apply updates
    for key, value in task_update.dict(exclude_unset=True).items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task

@app.delete("/tasks/{id}")
def delete_task(id: int, db: Session = Depends(get_db)):
    task = db.query(TaskDB).filter(TaskDB.id == id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return None

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
