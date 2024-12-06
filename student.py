from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from database import get_db
from models import Student, Class, Admin, Distribution, Subject, Teacher, Class_quiz, Questions, Quiz, Score
from auth import hash_password, get_current_user, verify_password
import uuid
from sqlalchemy import asc 
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from fastapi_pagination import Page, Params, paginate
from quiz import AnswerResponse, QuestionResponse, QuizDetailResponse
from collections import defaultdict
from config import imageprofile
from basemodel.StudentModel import StudentCreate, StudentResponse, StudentUpdate, QuizResponse, SubjectQuizzesResponse, StudentScoreResponse

router = APIRouter()

def update_total_students(class_id: int, db: Session):
    total_students = db.query(Student).filter(Student.class_id == class_id).count()
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if class_obj:
        class_obj.total_student = total_students
        db.commit()


# API route to retrieve all students
@router.get("/api/students", response_model=Page[StudentResponse], tags=["Students"])
def get_all_students(
    params: Params = Depends(),
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")

    # Fetch all students and their respective classes, sắp xếp theo mastudent tăng dần
    students = db.query(Student).order_by(asc(Student.mastudent)).all()
    # Check if no students are found
    if not students:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No students found")
         # Update the total students for each class
    class_ids = {student.class_id for student in students}  # Get unique class IDs
    for class_id in class_ids:
        update_total_students(class_id, db)
    # Compile list with student and class information
    student_list = []
    for student in students:
        classe = db.query(Class).filter(Class.class_id == student.class_id).first()
        student_info = {
            "student_id": student.student_id,
            "mastudent": student.mastudent,
            "gender": student.gender,
            "name": student.name,
            "birth_date": student.birth_date,
            "email": student.email,
            "phone_number": student.phone_number,
            "image": student.image,
            "class_id": student.class_id,
            "name_class": classe.name_class if classe else "Unknown",
            "first_login": student.first_login

        }
        student_list.append(student_info)
    # Paginate and return the response
    return paginate(student_list, params)
    
#Chi tiết người dùng
@router.get("/api/student/{student_id}", response_model=StudentResponse, tags=["Students"])
def get_student_details(
    student_id: str,
    db: Session = Depends(get_db),
    current_user: Admin = Depends(get_current_user)
):
    # Kiểm tra quyền truy cập của người dùng (chỉ admin mới được phép)
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    # Tìm học sinh theo student_id
    student = db.query(Student).filter(Student.student_id == student_id).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")
    # Lấy thông tin lớp học của học sinh
    classe = db.query(Class).filter(Class.class_id == student.class_id).first()
    # Tạo dữ liệu trả về
    student_info = StudentResponse(
        student_id=student.student_id,
        mastudent=student.mastudent,
        gender=student.gender,
        name=student.name,
        birth_date=student.birth_date,
        email=student.email,
        phone_number=student.phone_number,
        image=student.image,
        class_id=student.class_id,
        name_class=classe.name_class if classe else "Unknown",
        first_login=student.first_login
    )
    return student_info



@router.post("/api/post/students", tags=["Students"])
def create_student(
    student_data: StudentCreate, 
    db: Session = Depends(get_db), 
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    # Check if the class exists
    class_info = db.query(Class).filter(Class.class_id == student_data.class_id).first()
    if not class_info:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")
    # Check if the student already exists
    existing_student = db.query(Student).filter(Student.mastudent == student_data.mastudent).first()
    if existing_student:
        raise HTTPException(status_code=400, detail="Mã học sinh đã tồn tại")
    new_student = Student(
        student_id=str(uuid.uuid4()),
        mastudent=student_data.mastudent,
        name=student_data.name,
        gender=student_data.gender,
        birth_date=student_data.birth_date,
        email=student_data.email,
        phone_number=student_data.phone_number,
        class_id=student_data.class_id,
        password=hash_password(student_data.password),
        image=imageprofile,
        first_login=True
    )
    try:
        db.add(new_student)
        db.commit()
        db.refresh(new_student)
        update_total_students(student_data.class_id, db)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã học sinh hoặc email đã tồn tại")
    
    return {"message": "Tạo tài khoản học sinh thành công", "student_id": new_student.student_id}

@router.put("/api/put/students/{student_id}", tags=["Students"])
def update_student(
    student_data: StudentUpdate, 
    db: Session = Depends(get_db), 
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    student = db.query(Student).filter(Student.student_id == student_data.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh")
    if student_data.mastudent is not None:
        student.mastudent = student_data.mastudent
    if student_data.name is not None:
        student.name = student_data.name
    if student_data.gender is not None:
        student.gender = student_data.gender
    if student_data.birth_date is not None:
        student.birth_date = student_data.birth_date
    if student_data.email is not None:
        existing_email = db.query(Student).filter(Student.email == student_data.email, Student.student_id != student_data.student_id).first()
        if existing_email:
            raise HTTPException(status_code=400, detail="Email đã tồn tại")
        student.email = student_data.email
    if student_data.phone_number is not None:
        student.phone_number = student_data.phone_number
    if student_data.class_id is not None:
        class_info = db.query(Class).filter(Class.class_id == student_data.class_id).first()
        if not class_info:
            raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")
        student.class_id = student_data.class_id
        update_total_students(student_data.class_id, db)
    try:
        db.commit()
        db.refresh(student)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Đã xảy ra lỗi khi cập nhật thông tin học sinh")
    return {"message": "Cập nhật thông tin học sinh thành công", "student_id": student.student_id}

# API tìm kiếm học sinh với phân trang
@router.get("/api/search/students", response_model=Page[StudentResponse], tags=["Students"])
def search_students(
    name: str, 
    db: Session = Depends(get_db), 
    params: Params = Depends(),
    current_user: Admin = Depends(get_current_user)
):
    if not isinstance(current_user, Admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins can access this resource")
    students = db.query(Student).filter(Student.name.ilike(f"%{name}%")).all()
    if not students:
        raise HTTPException(status_code=200, detail="Không tìm thấy học sinh nào")
    student_data = []
    for student in students:
        classe = db.query(Class).filter(Class.class_id == student.class_id).first()
        student_info = {
            "student_id": student.student_id,
            "mastudent": student.mastudent,
            "name": student.name,
            "gender": student.gender,
            "birth_date": student.birth_date,
            "email": student.email,
            "phone_number": student.phone_number,
            "image": student.image,
            "class_id": student.class_id,
            "name_class": classe.name_class if classe else "Không rõ",
            "first_login": student.first_login
        }
        student_data.append(student_info)
    return paginate(student_data, params)

# API lấy thông tin học sinh, lớp, môn học và giáo viên
@router.get("/api/students/class_subject", tags=["Students"])
def get_student_class_subject_teacher(
    db: Session = Depends(get_db), 
    current_user: Student = Depends(get_current_user)  
):
    student = db.query(Student).filter(Student.student_id == current_user.student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy học sinh")
    class_info = db.query(Class).filter(Class.class_id == student.class_id).first()
    if not class_info:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học")
    distributions = db.query(Distribution).filter(Distribution.class_id == student.class_id).all()
    if not distributions:
        raise HTTPException(status_code=404, detail="Không có môn học nào cho lớp này")
    class_info_data = {
        "class_id": class_info.class_id,
        "name_class": class_info.name_class
    }
    subjects_data = []
    for distribution in distributions:
        teacher = db.query(Teacher).filter(Teacher.teacher_id == distribution.teacher_id).first()
        subject = db.query(Subject).filter(Subject.subject_id == teacher.subject_id).first()
        subjects_data.append({
            "subject_id": subject.subject_id,
            "subject_image": subject.image,
            "subject_name": subject.name_subject,
            "teacher": {
                "teacher_id": teacher.teacher_id,
                "name": teacher.name,
            }
        })
    return {
        "student_id": student.student_id,
        "class": class_info_data,
        "subjects": subjects_data
    }

@router.get("/api/quizzes/{subject_id}", response_model=Page[dict], tags=["Students"]) 
def get_quizzes_by_subject(
    subject_id: int,
    params: Params = Depends(),
    db: Session = Depends(get_db),
    current_user: Student = Depends(get_current_user)
):
    # Kiểm tra nếu người dùng không phải là học sinh
    if not isinstance(current_user, Student):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only students can access their quizzes.")
    
    # Lấy danh sách quiz cho lớp học của học sinh
    class_quiz_ids = db.query(Class_quiz.quiz_id).filter(Class_quiz.class_id == current_user.class_id).subquery()
    
    # Lấy các quiz thuộc subject_id và nằm trong lớp của học sinh, sắp xếp theo due_date giảm dần
    quizzes = db.query(Quiz).join(Teacher, Quiz.teacher_id == Teacher.teacher_id) \
                .filter(Teacher.subject_id == subject_id, Quiz.quiz_id.in_(class_quiz_ids)) \
                .order_by(Quiz.due_date.desc()).all()
    
    # Lấy điểm của học sinh cho các quiz này
    scores = db.query(Score).filter(Score.student_id == current_user.student_id).all()
    score_dict = {score.quiz_id: score for score in scores}
    
    if not quizzes:
        raise HTTPException(status_code=404, detail="No quizzes available for this subject and student class.")
    
    # Chuẩn bị danh sách chi tiết cho từng quiz
    quiz_details = []
    for quiz in quizzes:
        score_entry = score_dict.get(quiz.quiz_id, None)
        
        # Xác định trạng thái quiz
        if score_entry:
            if score_entry.status == "Completed":
                status = "Completed"
            elif score_entry.time_end and datetime.now() < score_entry.time_end:
                status = "Continues"  # Nếu thời gian kết thúc chưa qua và quiz đang tiếp tục
            elif quiz.due_date > datetime.now():
                status = "Ongoing"  # Nếu quiz đang tiếp diễn
            else:
                status = "Expired"  # Nếu quiz đã hết hạn
        else:
            # Nếu không có điểm, kiểm tra thời gian kết thúc
            status = "Ongoing" if quiz.due_date > datetime.now() else "Expired"
        
        score = None
        
        # Nếu quiz đã hết hạn mà học sinh chưa làm bài, điểm là 0
        if status == "Expired" and score_entry is None:
            score = 0  # Điểm là 0 vì quiz đã hết hạn và học sinh chưa làm bài
            new_score = Score(
                student_id=current_user.student_id,
                quiz_id=quiz.quiz_id,
                score=score
            )
            db.add(new_score)
            db.commit()
        elif score_entry:
            # Kiểm tra nếu time_end đã qua và chưa có điểm
            if score_entry.score is None and score_entry.time_end and datetime.now() > score_entry.time_end:
                score = 0  # Nếu thời gian kết thúc đã qua mà chưa có điểm, điểm = 0
                score_entry.score = score  # Cập nhật điểm
                score_entry.status = "Completed"
                db.commit()
            else:
                score = score_entry.score  # Lấy điểm đã lưu trong bảng Score
        
        quiz_info = {
            "quiz_id": quiz.quiz_id,
            "title": quiz.title,
            "due_date": quiz.due_date,
            "time_limit": quiz.time_limit,
            "question_count": quiz.question_count,
            "status": status,
            "score": score,
            "teacher_id": quiz.teacher_id
        }
        quiz_details.append(quiz_info)
    
    return paginate(quiz_details, params)


# API to get students and scores by class_id
@router.get("/api/class/{class_id}/students-scores", response_model=List[StudentScoreResponse], tags=["Students"])
def get_class_students_scores(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: Teacher = Depends(get_current_user)
):
    # Xác nhận người dùng có quyền truy cập
    if not isinstance(current_user, Teacher):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teacher can access this resource")
    
    # Kiểm tra nếu lớp tồn tại
    class_obj = db.query(Class).filter(Class.class_id == class_id).first()
    if not class_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
    
    # Lấy danh sách học sinh trong lớp
    students = db.query(Student).filter(Student.class_id == class_id).all()
    if not students:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No students found in this class")
    
    # Lấy danh sách các quiz của lớp và sắp xếp theo due_date giảm dần
    quizzes = db.query(Quiz).join(Class_quiz, Quiz.quiz_id == Class_quiz.quiz_id).filter(
        Class_quiz.class_id == class_id, 
        Quiz.teacher_id == current_user.teacher_id
    ).order_by(Quiz.due_date.desc()).all()
    
    quiz_titles = {quiz.quiz_id: quiz.title for quiz in quizzes}
    
    # Tạo kết quả cho từng học sinh
    student_scores = []
    for student in students:
        # Lấy điểm của học sinh cho các quiz
        scores = db.query(Score).filter(Score.student_id == student.student_id, Score.quiz_id.in_(quiz_titles.keys())).all()
        score_dict = {quiz_titles[score.quiz_id]: score.score for score in scores}
        
        # Đảm bảo tất cả các quiz đều có mặt trong score_dict, nếu không thì thêm null hoặc 0
        for quiz_id, quiz_title in quiz_titles.items():
            if quiz_title not in score_dict:
                # Tìm quiz trong quiz_titles để kiểm tra thời gian kết thúc và trạng thái quiz
                quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
                if quiz:
                    # Xử lý trạng thái quiz dựa trên time_end và thời gian hiện tại
                    score_dict[quiz_title] = None
                    if quiz.due_date < datetime.now():  # Nếu quiz đã hết hạn
                        score_dict[quiz_title] = 0  # Gán điểm là 0 nếu quiz đã hết hạn
                    # Kiểm tra nếu quiz đã hết hạn nhưng học sinh chưa làm bài
                    score_entry = db.query(Score).filter(Score.student_id == student.student_id, Score.quiz_id == quiz_id).first()
                    if score_entry and score_entry.time_end and datetime.now() > score_entry.time_end and score_entry.score is None:
                        score_dict[quiz_title] = 0  # Điểm = 0 nếu thời gian kết thúc đã qua và học sinh chưa làm bài

        # Thêm vào danh sách kết quả
        student_scores.append(StudentScoreResponse(
            student_id=student.student_id,
            student_name=student.name,
            scores=score_dict
        ))

    return student_scores
