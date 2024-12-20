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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    # Kiểm tra xem môn học có tồn tại không
    subject_info = db.query(Subject).filter(Subject.subject_id == teacher_data.subject_id).first()
    if not subject_info:
        raise HTTPException(status_code=404, detail="Không tìm thấy môn học")
    # Kiểm tra xem giáo viên đã tồn tại chưa
    existing_teacher = db.query(Teacher).filter(Teacher.mateacher == teacher_data.mateacher).first()
    if existing_teacher:
        raise HTTPException(status_code=400, detail="Mã giáo viên đã tồn tại")
    existing_email = db.query(Teacher).filter(Teacher.email == teacher_data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email đã tồn tại")
    # Tạo giáo viên mới
    new_teacher = Teacher(
        teacher_id=str(uuid.uuid4()),  # Tạo UUID ngẫu nhiên cho teacher_id
        mateacher=teacher_data.mateacher,
        name=teacher_data.name,
        gender=teacher_data.gender,
        birth_date=teacher_data.birth_date,
        email=teacher_data.email,
        phone_number=teacher_data.phone_number,
        subject_id=teacher_data.subject_id,
        password=hash_password(teacher_data.password),  # Mã hóa mật khẩu
        image=imageprofile  # Ảnh mặc định
    )
    try:
        db.add(new_teacher)
        db.commit()
        db.refresh(new_teacher)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã giáo viên hoặc email đã tồn tại")
    # Phân công giáo viên vào các lớp học
    for class_id in teacher_data.class_ids:
        _class = db.query(Class).filter(Class.class_id == class_id).first()
        if not _class:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy lớp với ID {class_id}")
        # Tạo phân công mới giữa giáo viên và lớp
        new_distribution = Distribution(
            class_id=class_id,
            teacher_id=new_teacher.teacher_id  # Sử dụng teacher_id của giáo viên đã lưu
        )
        db.add(new_distribution)
    db.commit()  # Lưu phân công lớp học vào cơ sở dữ liệu
    return {
        "message": "Tạo tài khoản giáo viên và phân công lớp thành công",
        "teacher_id": new_teacher.teacher_id, 
        "mateacher": new_teacher.mateacher
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
