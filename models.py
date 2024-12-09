from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey, VARCHAR,Text, Float, func
from database import Base
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import relationship
def get_vietnam_time():
    utc_time = datetime.now()
    vietnam_time = utc_time + timedelta(hours=7)
    return vietnam_time
class Admin(Base):
    __tablename__ = "admin"
    admin_id = Column(String(36), primary_key=True)
    password = Column(VARCHAR(255), nullable=False)

class Subject(Base):
    __tablename__ = "subject"
    subject_id = Column(Integer, primary_key=True, autoincrement=True)
    name_subject = Column(VARCHAR(255), nullable=False)
    image = Column(VARCHAR(255), nullable=False)

class Teacher(Base):
    __tablename__ = "teacher"
    teacher_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mateacher = Column(VARCHAR(255), nullable=False)
    password = Column(VARCHAR(255), nullable=False)
    gender = Column(VARCHAR(255), nullable=False)
    name = Column(VARCHAR(255), nullable=False)
    birth_date = Column(DateTime, nullable=False)
    email = Column(VARCHAR(255), nullable=False)
    phone_number = Column(VARCHAR(15))
    image = Column(VARCHAR(255))
    image_id = Column(VARCHAR(255))
    image_delete_hash = Column(VARCHAR(255))
    reset_code = Column(VARCHAR(255))
    resetPasswordExpiry = Column(DateTime)
    subject_id = Column(Integer, ForeignKey('subject.subject_id'), nullable=False)

class Grades(Base):
    __tablename__ = "grades"
    id_grades = Column(Integer, primary_key=True, autoincrement=True)
    name_grades = Column(VARCHAR(255), nullable=False)

class Class(Base):
    __tablename__ = "class"
    class_id = Column(Integer, primary_key=True, autoincrement=True)
    name_class = Column(VARCHAR(255), nullable=False)
    years = Column(String(36))
    total_student = Column(Integer)
    id_grades = Column(Integer, ForeignKey('grades.id_grades'), nullable=False)

class Student(Base):
    __tablename__ = "student"
    student_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mastudent = Column(VARCHAR(255), nullable=False)
    password = Column(VARCHAR(255), nullable=False)
    gender = Column(VARCHAR(255), nullable=False)
    name = Column(VARCHAR(255), nullable=False)
    birth_date = Column(DateTime, nullable=False)
    email = Column(VARCHAR(255), nullable=False)
    phone_number = Column(VARCHAR(15))
    image = Column(VARCHAR(255))
    image_id = Column(VARCHAR(255))
    image_delete_hash = Column(VARCHAR(255))
    reset_code = Column(VARCHAR(255))
    resetPasswordExpiry = Column(DateTime)
    class_id = Column(Integer, ForeignKey('class.class_id'), nullable=False)
    first_login = Column(Boolean, default=True)

class Distribution(Base):
    __tablename__ = "distribution"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id = Column(Integer, ForeignKey('class.class_id'), nullable=False)
    teacher_id = Column(String(36), ForeignKey('teacher.teacher_id'), nullable=False)
    
class Quiz(Base):
    __tablename__ = 'quiz'
    quiz_id = Column(String(36),primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String)
    due_date = Column(DateTime)
    time_limit = Column(Integer)
    question_count = Column(Integer)
    teacher_id = Column(String(36), ForeignKey('teacher.teacher_id'))
    

class Questions(Base):
    __tablename__ = 'questions'
    question_id = Column(String(36),primary_key=True, default=lambda: str(uuid.uuid4()))
    quiz_id = Column(String(36), ForeignKey('quiz.quiz_id'))
    question_text= Column(Text, nullable=False)
    
class Answer(Base):
    __tablename__ = 'answer'
    answer_id = Column(String(36),primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id = Column(String(36), ForeignKey('questions.question_id'))
    answer = Column(Text)
    is_correct = Column(Boolean, default=True)
    
class Score(Base):
    __tablename__ = 'score'
    score_id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    student_id = Column(String(36), ForeignKey('student.student_id'))
    quiz_id = Column(String(36), ForeignKey('quiz.quiz_id'))
    score = Column(Float, nullable=True)
    time_start = Column(DateTime, nullable=True)
    time_end = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    
class Class_quiz(Base):
     __tablename__ = 'class_quiz'
     class_quiz_id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
     class_id = Column(Integer, ForeignKey('class.class_id'))   
     quiz_id = Column(String(36), ForeignKey('quiz.quiz_id'))
     
class Choice(Base):
    __tablename__ = 'choice'
    choice_id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    answer_id = Column(String(36), ForeignKey('answer.answer_id'), nullable=True)
    student_id = Column(String(36), ForeignKey('student.student_id'))
    
class Notification(Base):
    __tablename__ = 'notification'
    noti_id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    context = Column(Text)
    time = Column(DateTime)
    teacher_id = Column(String(36), ForeignKey('teacher.teacher_id'), nullable=True)
    student_id = Column(String(36), ForeignKey('student.student_id'), nullable=True)
    
class Feedback(Base):
    __tablename__ = 'feedback'
    feedback_id = Column(String(36), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    context = Column(Text)
    teacher_id = Column(String(36), ForeignKey('teacher.teacher_id'), nullable=True)
    student_id = Column(String(36), ForeignKey('student.student_id'), nullable=True)
    class_id = Column(Integer, ForeignKey('class.class_id'), nullable=False)  # Bắt buộc phải có lớp
    subject_id = Column(Integer, ForeignKey('subject.subject_id'), nullable=False)  # Bắt buộc phải có môn học
    is_parents = Column(Integer, default=0)  # 0 là feedback cha, 1 là feedback con
    parent_id = Column(String(36), nullable=True)  # Chỉ điền khi là feedback con
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time)
