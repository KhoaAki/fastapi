from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List,  Optional
from pydantic import BaseModel
from database import get_db
from models import Student, Class, Grades, Admin, Teacher, Distribution, Subject
from auth import hash_password, get_current_user
import uuid
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from student import update_total_students

router = APIRouter()
#API lấy class
@router.get("/api/classes", tags=["Classes"])
def get_all_grades_and_classes(
    db: Session = Depends(get_db), 
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    grades = db.query(Grades).all()
    if not grades:
        raise HTTPException(status_code=404, detail="Không tìm thấy khối nào")
    grades_data = []
    for grade in grades:
        # Fetch all classes for the current grade
        classes = db.query(Class).filter(Class.id_grades == grade.id_grades).all()
        # Update total students for each class
        for classe in classes:
            update_total_students(classe.class_id, db)
        # Prepare class data with updated total_student
        class_data = [
            {
                "class_id": classe.class_id,
                "name_class": classe.name_class,
                "total_student": classe.total_student
            }
            for classe in classes
        ]
        # Add grade and its classes to the response
        grades_data.append({
            "grade_id": grade.id_grades,
            "grade_name": grade.name_grades,
            "classes": class_data
        })
    return {
        "grades": grades_data
    }

# API lấy thông tin cả giáo viên và học sinh theo lớp
@router.get("/api/classes/{class_id}", tags=["Classes"])
def get_class_details(class_id: int, db: Session = Depends(get_db), current_user: Admin = Depends(get_current_user)):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    classe = db.query(Class).filter(Class.class_id == class_id).first()
    if not classe:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")
    students = db.query(Student).filter(Student.class_id == class_id).all()
    distributions = db.query(Distribution).filter(Distribution.class_id == class_id).all()
    student_data = []
    for student in students:
        student_data.append({
            "student_id": student.mastudent,
            "name": student.name,
            "gender": student.gender,
            "birth_date": student.birth_date,
            "email":student.email,
            "phone_number": student.phone_number,
            "image": student.image
        })
    teacher_data = []
    for dist in distributions:
        teacher = db.query(Teacher).filter(Teacher.teacher_id == dist.teacher_id).first()
        if teacher:
            subject = db.query(Subject).filter(Subject.subject_id == teacher.subject_id).first()
            teacher_data.append({
                "teacher_id": teacher.mateacher,
                "name": teacher.name,
                "gender": teacher.gender,
                "birth_date": teacher.birth_date,
                "email": teacher.email,
                "phone_number": teacher.phone_number,
                "name_subject": subject.name_subject if subject else "Không rõ"
            })
    return {
        "class_id": classe.class_id,
        "name_class": classe.name_class,
        "teachers": teacher_data,
        "students": student_data
    }
    
# API lấy thông tin các lớp học mà giáo viên phụ trách
@router.get("/api/teacher/classes", tags=["Classes"])
def get_teacher_classes(
    db: Session = Depends(get_db), 
    current_user: Teacher = Depends(get_current_user)  # Xác nhận current_user là giáo viên
):
    # Lấy thông tin giáo viên từ current_user
    teacher = db.query(Teacher).filter(Teacher.teacher_id == current_user.teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Can not find teacher")
    # Lấy thông tin các lớp mà giáo viên phụ trách từ bảng Distribution
    distributions = db.query(Distribution).filter(Distribution.teacher_id == teacher.teacher_id).all()
    if not distributions:
        raise HTTPException(status_code=404, detail="This teacher is not in charge of any classes")
    # Tạo danh sách các lớp
    classes_data = []
    for distribution in distributions:
        class_info = db.query(Class).filter(Class.class_id == distribution.class_id).first()
        if class_info:
            classes_data.append({
                "class_id": class_info.class_id,
                "name_class": class_info.name_class,
                "total_student": class_info.total_student
            })
    # Sắp xếp các lớp theo name_class tăng dần
    classes_data.sort(key=lambda x: x['name_class'])
    return {
        "teacher_id": teacher.teacher_id,
        "mateacher": teacher.mateacher,
        "teacher_name": teacher.name,
        "classes": classes_data
    }
    
# API lấy thông tin student theo lớp
@router.get("/api/teachers/classes/{class_id}", tags=["Classes"])
def get_classes(
    class_id: int, 
    db: Session = Depends(get_db), 
    current_user: Teacher = Depends(get_current_user)
):
    # Ensure only the teacher responsible for the class can access the data
    if not isinstance(current_user, Teacher):
        raise HTTPException(status_code=403, detail="Access forbidden: Only teachers can view class students")
    # Check if the teacher is assigned to the class
    distribution = db.query(Distribution).filter(
        Distribution.teacher_id == current_user.teacher_id,
        Distribution.class_id == class_id
    ).first()
    if not distribution:
        raise HTTPException(status_code=403, detail="Access forbidden: You are not assigned to this class")
    # Fetch class information
    classe = db.query(Class).filter(Class.class_id == class_id).first()
    if not classe:
        raise HTTPException(status_code=404, detail="Class not found")
    # Fetch students in the class
    students = db.query(Student).filter(Student.class_id == class_id).all()
    if not students:
        raise HTTPException(status_code=404, detail="No students found in this class")
    # Prepare student data
    student_data = []
    for student in students:
        student_data.append({
            "student_id": student.student_id,
            "name": student.name,
            "gender": student.gender,
            "birth_date": student.birth_date,
            "email": student.email,
            "phone_number": student.phone_number,
        })
    return {
        "class_id": classe.class_id,
        "name_class": classe.name_class,
        "students": student_data
    }

