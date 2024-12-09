from typing import List, Optional, Union
from pydantic import BaseModel
from database import get_db
from datetime import datetime, timedelta

def current_time():
    return datetime.utcnow() + timedelta(hours=7)

class FeedbackReply(BaseModel):
    feedback_id: str
    context: str
    teacher_id: Optional[str] = None
    student_id: Optional[str] = None
    class_id: int
    subject_id: int
    is_parents: int
    parent_id: Optional[str] = None
    created_at: datetime
    teacher_name: Optional[str] = None
    student_name: Optional[str] = None
    name_subject: Optional[str] = None  # Tên môn học


class FeedbackResponse(BaseModel):
    feedback_id: str
    context: str
    teacher_id: Optional[str] = None
    student_id: Optional[str] = None
    class_id: int
    subject_id: int
    is_parents: int
    parent_id: Optional[str] = None
    created_at: datetime
    replies: List[FeedbackReply] = []  # Danh sách phản hồi con
    teacher_name: Optional[str] = None
    student_name: Optional[str] = None
    name_subject: Optional[str] = None  # Tên môn học


class FeedbackCreate(BaseModel):
    context: str
    subject_id: Optional[int] = None
    class_id: Optional[int] = None
    parent_id: Optional[str] = None
    created_at: datetime = current_time()
