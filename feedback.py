from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from pydantic import BaseModel
from database import get_db
from models import Teacher, Subject, Admin, Class, Distribution, Feedback, Student, Notification
from auth import get_current_user
import uuid
from datetime import datetime
from basemodel.FeedbackModel import FeedbackReply, FeedbackResponse, FeedbackCreate

router = APIRouter()
# API Endpoints
@router.get("/api/feedback", response_model=List[FeedbackResponse], tags=["Feedback"])
def get_feedback(
    class_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Union[Student, Teacher, Admin] = Depends(get_current_user),
):
    # Xác định quyền hạn của người dùng
    if isinstance(current_user, Student):
        class_id = current_user.class_id
        if not subject_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide subject to access",
            )
    elif isinstance(current_user, Teacher):
        subject_id = current_user.subject_id
        if not class_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide class to access",
            )
        class_assigned = db.query(Distribution).filter(
            Distribution.class_id == class_id,
            Distribution.teacher_id == current_user.teacher_id,
        ).first()
        if not class_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this class",
            )
    elif not isinstance(current_user, Admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students, teachers, and administrators can view feedback.",
        )
    # Truy vấn danh sách feedback
    feedback_list = db.query(Feedback).filter_by(class_id=class_id, subject_id=subject_id).order_by(Feedback.created_at.desc()).all()
    # Tạo danh sách phản hồi chính và trả lời
    feedback_dict = {}
    unlinked_replies = []  # Danh sách phản hồi chưa liên kết
    for fb in feedback_list:
        teacher_name = None
        student_name = None
        if fb.teacher_id:
            teacher = db.query(Teacher).filter_by(teacher_id=fb.teacher_id).first()
            teacher_name = teacher.name if teacher else None
        if fb.student_id:
            student = db.query(Student).filter_by(student_id=fb.student_id).first()
            student_name = student.name if student else None
        if fb.is_parents == 0:  # Phản hồi chính
            feedback_dict[fb.feedback_id] = FeedbackResponse(
                feedback_id=fb.feedback_id,
                context=fb.context,
                teacher_id=fb.teacher_id,
                student_id=fb.student_id,
                class_id=fb.class_id,
                subject_id=fb.subject_id,
                is_parents=fb.is_parents,
                parent_id=fb.parent_id,
                created_at=fb.created_at,
                replies=[],
                teacher_name=teacher_name,
                student_name=student_name,
                name_subject=None,  # Môn học sẽ được thêm sau
            )
        else:  # Phản hồi phụ
            # Kiểm tra xem parent_id có tồn tại trong feedback_dict không
            if fb.parent_id in feedback_dict:
                feedback_dict[fb.parent_id].replies.append(
                    FeedbackReply(
                        feedback_id=fb.feedback_id,
                        context=fb.context,
                        teacher_id=fb.teacher_id,
                        student_id=fb.student_id,
                        class_id=fb.class_id,
                        subject_id=fb.subject_id,
                        is_parents=fb.is_parents,
                        parent_id=fb.parent_id,
                        created_at=fb.created_at,
                        teacher_name=teacher_name,
                        student_name=student_name,
                        name_subject=None,
                    )
                )
            else:
                # Lưu trữ phản hồi chưa liên kết
                unlinked_replies.append(fb)
    # Liên kết các reply chưa được gắn
    for reply in unlinked_replies:
        teacher_name = None
        student_name = None
        if fb.teacher_id:
            teacher = db.query(Teacher).filter_by(teacher_id=reply.teacher_id).first()
            teacher_name = teacher.name if teacher else None
        if fb.student_id:
            student = db.query(Student).filter_by(student_id=reply.student_id).first()
            student_name = student.name if student else None
        if reply.parent_id in feedback_dict:
            feedback_dict[reply.parent_id].replies.append(
                FeedbackReply(
                    feedback_id=reply.feedback_id,
                    context=reply.context,
                    teacher_id=reply.teacher_id,
                    student_id=reply.student_id,
                    class_id=reply.class_id,
                    subject_id=reply.subject_id,
                    is_parents=reply.is_parents,
                    parent_id=reply.parent_id,
                    created_at=reply.created_at,
                    teacher_name=teacher_name,  # Có thể bổ sung nếu cần
                    student_name=student_name,  # Có thể bổ sung nếu cần
                    name_subject=None,
                )
            )
    # Sắp xếp các phản hồi phụ theo thời gian
    for feedback in feedback_dict.values():
        feedback.replies.sort(key=lambda reply: reply.created_at, reverse=True)
    # Cập nhật thông tin môn học
    if subject_id:
        subject = db.query(Subject).filter(Subject.subject_id == subject_id).first()
        name_subject = subject.name_subject if subject else "Unknown"
        for fb_id in feedback_dict:
            feedback_dict[fb_id].name_subject = name_subject
            for reply in feedback_dict[fb_id].replies:
                reply.name_subject = name_subject
    return list(feedback_dict.values())


@router.post("/api/post/feedback", response_model=FeedbackResponse, tags=["Feedback"])
def create_feedback(
    feedback: FeedbackCreate,
    db: Session = Depends(get_db),
    current_user: Union[Student, Teacher] = Depends(get_current_user),
):
    if isinstance(current_user, Student):
        feedback.class_id = current_user.class_id
        if not feedback.subject_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide subject to access")
        student = db.query(Student).filter(
            Student.student_id == current_user.student_id,
            Student.class_id == feedback.class_id
        ).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have any permission")
    elif isinstance(current_user, Teacher):
        feedback.subject_id = current_user.subject_id
        if not feedback.class_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Provide class to access")
        class_assigned = db.query(Distribution).filter(
            Distribution.class_id == feedback.class_id,
            Distribution.teacher_id == current_user.teacher_id
        ).first()
        if not class_assigned:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have any permission")
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ học sinh và giáo viên mới có quyền tạo phản hồi.")

    is_parents = 1 if feedback.parent_id else 0
    new_feedback = Feedback(
        context=feedback.context,
        teacher_id=current_user.teacher_id if isinstance(current_user, Teacher) else None,
        student_id=current_user.student_id if isinstance(current_user, Student) else None,
        class_id=feedback.class_id,
        subject_id=feedback.subject_id,
        is_parents=is_parents,
        parent_id=feedback.parent_id,
    )
    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    # Gửi thông báo
    if feedback.parent_id:
        # Trả lời một phản hồi
        parent_feedback = db.query(Feedback).filter(Feedback.feedback_id == feedback.parent_id).first()
        if not parent_feedback:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent feedback not found")
        # Xác định người nhận thông báo
        recipient = None
        if parent_feedback.student_id:
            recipient = db.query(Student).filter(Student.student_id == parent_feedback.student_id).first()
        elif parent_feedback.teacher_id:
            recipient = db.query(Teacher).filter(Teacher.teacher_id == parent_feedback.teacher_id).first()
        # Tạo nội dung thông báo
        if recipient:
            notification_context = f"{current_user.name} đã trả lời phản hồi của bạn: {feedback.context[:50]}..."
            new_notification = Notification(
                context=notification_context,
                student_id=recipient.student_id if isinstance(recipient, Student) else None,
                teacher_id=recipient.teacher_id if isinstance(recipient, Teacher) else None
            )
            db.add(new_notification)
    else:
        # Logic gửi thông báo như trước
        if isinstance(current_user, Student):
            # Gửi thông báo đến giáo viên phụ trách lớp/môn
            student_class = db.query(Class).filter(Class.class_id == current_user.class_id).first()
            class_name = student_class.name_class if student_class else "không xác định"
            notification_context = f"Phản hồi hỗ trợ mới từ học sinh {current_user.name} - Lớp: {class_name}."
            teacher = db.query(Teacher).filter(Teacher.subject_id == feedback.subject_id).first()
            if teacher:
                new_notification = Notification(
                    context=notification_context,
                    teacher_id=teacher.teacher_id,
                    student_id=None  # Không cần thiết
                )
                db.add(new_notification)
        elif isinstance(current_user, Teacher):
            # Gửi thông báo đến tất cả học sinh trong lớp
            subject = db.query(Subject).filter(Subject.subject_id == feedback.subject_id).first()
            subject_name = subject.name_subject if subject else "không xác định"
            notification_context = f"Phản hồi hỗ trợ mới từ giáo viên {current_user.name} - Môn: {subject_name}."
            students = db.query(Student).filter(Student.class_id == feedback.class_id).all()
            for student in students:
                new_notification = Notification(
                    context=notification_context,
                    student_id=student.student_id,
                    teacher_id=None  # Không cần thiết
                )
                db.add(new_notification)
    db.commit()
    # Trả về phản hồi
    subject = db.query(Subject).filter(Subject.subject_id == feedback.subject_id).first()
    name_subject = subject.name_subject if subject else None
    teacher_name = current_user.name if isinstance(current_user, Teacher) else None
    student_name = current_user.name if isinstance(current_user, Student) else None
    return FeedbackResponse(
        feedback_id=new_feedback.feedback_id,
        context=new_feedback.context,
        teacher_id=new_feedback.teacher_id,
        student_id=new_feedback.student_id,
        class_id=new_feedback.class_id,
        subject_id=new_feedback.subject_id,
        is_parents=new_feedback.is_parents,
        parent_id=new_feedback.parent_id,
        created_at=new_feedback.created_at,
        replies=[],
        teacher_name=teacher_name,
        student_name=student_name,
        name_subject=name_subject
    )
