from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Union
from pydantic import BaseModel
from database import get_db
from models import Teacher, Subject, Admin, Class, Distribution
from auth import hash_password, get_current_user
import uuid
from sqlalchemy import asc 
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from fastapi_pagination import Page, Params, paginate
from config import imageprofile
from basemodel.TeacherModel import TeacherCreate, TeacherResponse, TeacherUpdate
router = APIRouter()

# API route to retrieve all teachers with their subject and class information
@router.get("/api/teachers", response_model=Page[TeacherResponse], tags=["Teachers"])
def get_all_teachers(
    params: Params = Depends(),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")

    # Fetch all teachers sorted by mateacher in ascending order
    teachers = db.query(Teacher).order_by(asc(Teacher.mateacher)).all()
    if not teachers:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No teachers found")
    teacher_data = []
    for teacher in teachers:
        subject = db.query(Subject).filter(Subject.subject_id == teacher.subject_id).first()
        distributions = db.query(Distribution).filter(Distribution.teacher_id == teacher.teacher_id).all()
        class_info = []
        for distribution in distributions:
            class_data = db.query(Class).filter(Class.class_id == distribution.class_id).first()
            if class_data:
                class_info.append({
                    "class_id": class_data.class_id,
                    "name_class": class_data.name_class
                })
        teacher_data.append({
            "teacher_id": teacher.teacher_id,
            "mateacher": teacher.mateacher,
            "gender": teacher.gender,
            "name": teacher.name,
            "birth_date": teacher.birth_date,
            "email": teacher.email,
            "phone_number": teacher.phone_number,
            "image": teacher.image,
            "subject": subject.name_subject if subject else "Unknown",
            "classes": class_info
        })

    # Paginate and return the response
    return paginate(teacher_data, params)   

# API route để lấy thông tin chi tiết một giáo viên
@router.get("/api/teachers/{teacher_id}", response_model=TeacherResponse, tags=["Teachers"])
def get_teacher_detail(
    teacher_id: str,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    subject = db.query(Subject).filter(Subject.subject_id == teacher.subject_id).first()
    distributions = db.query(Distribution).filter(Distribution.teacher_id == teacher.teacher_id).all()
    class_info = []
    for distribution in distributions:
        class_data = db.query(Class).filter(Class.class_id == distribution.class_id).first()
        if class_data:
            class_info.append({
                "class_id": class_data.class_id,
                "name_class": class_data.name_class
            })
    return {
        "teacher_id": teacher.teacher_id,
        "mateacher": teacher.mateacher,
        "gender": teacher.gender,
        "name": teacher.name,
        "birth_date": teacher.birth_date,
        "email": teacher.email,
        "phone_number": teacher.phone_number,
        "image": teacher.image,
        "subject": subject.name_subject if subject else "Unknown",
        "classes": class_info
    }

@router.post("/api/post/teachers", tags=["Teachers"])
def create_teacher(
    teacher_data: TeacherCreate, 
    db: Session = Depends(get_db), 
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=403, detail="Only admins can access this resource.")
    # Kiểm tra tồn tại môn học
    subject_info = db.query(Subject).filter(Subject.subject_id == teacher_data.subject_id).first()
    if not subject_info:
        raise HTTPException(status_code=404, detail="Subject not found.")
    # Kiểm tra trùng mã hoặc email giáo viên
    if db.query(Teacher).filter(Teacher.mateacher == teacher_data.mateacher).first():
        raise HTTPException(status_code=400, detail="Teacher code already exists.")
    if db.query(Teacher).filter(Teacher.email == teacher_data.email).first():
        raise HTTPException(status_code=400, detail="Email already exists.")
    # Danh sách lớp trùng
    conflicting_classes = []
    # Kiểm tra trước tất cả các lớp được yêu cầu
    for class_id in teacher_data.class_ids:
        _class = db.query(Class).filter(Class.class_id == class_id).first()
        if not _class:
            raise HTTPException(status_code=404, detail=f"Class with ID {class_id} not found.")
        # Kiểm tra lớp đã có giáo viên dạy môn học này chưa
        existing_distribution = db.query(Distribution).join(Teacher).filter(
            Distribution.class_id == class_id,
            Teacher.subject_id == teacher_data.subject_id
        ).first()
        if existing_distribution:
            conflicting_classes.append(_class.name_class)
    # Nếu có lớp bị trùng, trả về lỗi mà không lưu giáo viên
    if conflicting_classes:
        raise HTTPException(
            status_code=400,
            detail=f"The following classes already have a teacher assigned for this subject: {', '.join(conflicting_classes)}."
        )
    # Tạo giáo viên mới (sau khi chắc chắn không có lớp trùng)
    new_teacher = Teacher(
        teacher_id=str(uuid.uuid4()), 
        mateacher=teacher_data.mateacher,
        name=teacher_data.name,
        gender=teacher_data.gender,
        birth_date=teacher_data.birth_date,
        email=teacher_data.email,
        phone_number=teacher_data.phone_number,
        subject_id=teacher_data.subject_id,
        password=hash_password(teacher_data.password),  
        image=imageprofile  
    )
    db.add(new_teacher)
    db.commit()  # Lưu giáo viên vào cơ sở dữ liệu
    db.refresh(new_teacher)  # Làm mới đối tượng để đảm bảo dữ liệu mới nhất
    # Thực hiện phân công giáo viên vào lớp
    assigned_classes = []
    for class_id in teacher_data.class_ids:
        new_distribution = Distribution(
            class_id=class_id,
            teacher_id=new_teacher.teacher_id
        )
        db.add(new_distribution)
        assigned_classes.append(db.query(Class).filter(Class.class_id == class_id).first().name_class)
    try:
        db.commit()  # Lưu tất cả phân công vào cơ sở dữ liệu
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"IntegrityError: {str(e)}")
    return {
        "message": "Teacher created and assigned to classes successfully.",
        "teacher_id": new_teacher.teacher_id,
        "assigned_classes": assigned_classes
    }

@router.put("/api/put/teachers/{teacher_id}", tags=["Teachers"])
def update_teacher(
    teacher_data: TeacherUpdate, 
    db: Session = Depends(get_db), 
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    # Tìm giáo viên theo teacher_id
    teacher = db.query(Teacher).filter(Teacher.teacher_id == teacher_data.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy giáo viên")
    # Cập nhật các thông tin của giáo viên nếu có
    if teacher_data.mateacher is not None:
        teacher.mastudent = teacher_data.mateacher
    if teacher_data.name is not None:
        teacher.name = teacher_data.name
    if teacher_data.gender is not None:
        teacher.gender = teacher_data.gender
    if teacher_data.birth_date is not None:
        teacher.birth_date = teacher_data.birth_date
    if teacher_data.email is not None:
        existing_email = db.query(Teacher).filter(Teacher.email == teacher_data.email, Teacher.teacher_id != teacher_data.teacher_id).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email đã tồn tại")
        teacher.email = teacher_data.email
    if teacher_data.phone_number is not None:
        teacher.phone_number = teacher_data.phone_number
    if teacher_data.subject_id is not None:
        subject_info = db.query(Subject).filter(Subject.subject_id == teacher_data.subject_id).first()
        if not subject_info:
            raise HTTPException(status_code=404, detail="Không tìm thấy môn học")
        teacher.subject_id = teacher_data.subject_id
    # Cập nhật danh sách lớp của giáo viên nếu có
    if teacher_data.class_ids is not None:
        # Xóa các phân công lớp hiện tại của giáo viên
        db.query(Distribution).filter(Distribution.teacher_id == teacher.teacher_id).delete()
        # Phân công lại các lớp mới
        for class_id in teacher_data.class_ids:
            _class = db.query(Class).filter(Class.class_id == class_id).first()
            if not _class:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy lớp với ID {class_id}")
            new_distribution = Distribution(
                class_id=class_id,
                teacher_id=teacher.teacher_id  # Sử dụng teacher_id của giáo viên
            )
            db.add(new_distribution)
    try:
        db.commit()
        db.refresh(teacher)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Đã xảy ra lỗi khi cập nhật thông tin giáo viên")
    return {"message": "Cập nhật thông tin giáo viên thành công", "teacher_id": teacher.teacher_id}

# API tìm kiếm giáo viên với phân trang
@router.get("/api/search/teachers", response_model=Page[TeacherResponse], tags=["Teachers"])
def search_teachers(
    name: str, 
    db: Session = Depends(get_db), 
    params: Params = Depends(),
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    
    # Tìm kiếm giáo viên theo tên
    teachers = db.query(Teacher).filter(Teacher.name.ilike(f"%{name}%")).all()
    if not teachers:
        raise HTTPException(status_code=200, detail="Không tìm thấy giáo viên nào")
    teacher_data = []
    for teacher in teachers:
        # Lấy thông tin về môn học
        subject = db.query(Subject).filter(Subject.subject_id == teacher.subject_id).first()
        
        # Lấy thông tin về lớp
        distributions = db.query(Distribution).filter(Distribution.teacher_id == teacher.teacher_id).all()
        class_info = []
        for distribution in distributions:
            class_data = db.query(Class).filter(Class.class_id == distribution.class_id).first()
            if class_data:
                class_info.append({
                    "class_id": class_data.class_id,  # Giữ nguyên kiểu dữ liệu class_id
                    "name_class": class_data.name_class
                })
        
        teacher_info = {
            "teacher_id": teacher.teacher_id,  # Thêm trường teacher_id
            "mateacher": teacher.mateacher,
            "gender": teacher.gender,
            "name": teacher.name,
            "birth_date": teacher.birth_date,
            "email": teacher.email,
            "phone_number": teacher.phone_number,
            "image": teacher.image,
            "subject": subject.name_subject if subject else "Không rõ",
            "classes": class_info
        }
        teacher_data.append(teacher_info)

    return paginate(teacher_data, params)


@router.get("/api/teacher/subjects", tags=["Classes"])
def get_classes_for_teacher(db: Session = Depends(get_db), current_user: Admin = Depends(get_current_user)):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can access this resource")
    # Lấy tất cả các môn học
    subjects = db.query(Subject).all()
    if not subjects:
        raise HTTPException(status_code=404, detail="Không tìm thấy môn nào")
    subject_data = []
    for subject in subjects:
        subject_data.append({
            "subject_id": subject.subject_id,
            "name_subject": subject.name_subject,
        })
    return {
        "subjects": subject_data  }
