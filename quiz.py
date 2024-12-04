from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from sqlalchemy.sql import func, case
from pydantic import BaseModel
from database import get_db
from models import Teacher, Subject, Admin, Class, Distribution, Quiz, Class_quiz, Questions, Answer, Student, Choice, Score, Notification
from auth import hash_password, get_current_user
import uuid
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from fastapi_pagination import Page, Params, paginate
from basemodel.QuizModel import AnswerCreate, QuestionCreate, ClassAssignment, QuizWithQuestionsCreate, AnswerUpdate, QuestionUpdate, UpdateQuestion, AnswerResponse, QuestionResponse, QuizDetailResponse, AnswerSubmission, QuizSubmission, QuestionReview, QuizReviewResponse, QuizDetailResponse1,AnswerResponse1, QuestionResponse1, QuizSummaryResponse, QuizRequest
router = APIRouter()

#API lấy thông tin bài tập của giáo vin 
@router.get("/api/teacher/quizzes", response_model=Page[dict], tags=["Quizzes"])
def get_teacher_quizzes(
    db: Session = Depends(get_db), 
    params: Params = Depends(),
    current_user: Teacher = Depends(get_current_user)  # Ensure the current user is a teacher
):
    # Ensure the user is a teacher
    if not isinstance(current_user, Teacher):
        raise HTTPException(status_code=403, detail="Access forbidden: Only teachers can view their quizzes")
    # Fetch quizzes assigned to the current teacher
    quizzes = db.query(Quiz).filter(Quiz.teacher_id == current_user.teacher_id).all()
    # Check if there are no quizzes
    if not quizzes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No quizzes found")
    # Prepare a list of quizzes with additional information
    quiz_list = []
    for quiz in quizzes:
        class_quizzes = db.query(Class_quiz).filter(Class_quiz.quiz_id == quiz.quiz_id).all()
        class_ids = [class_quiz.class_id for class_quiz in class_quizzes] if class_quizzes else []
        class_names = db.query(Class.name_class).filter(Class.class_id.in_(class_ids)).all()
        class_names_list = [class_name[0] for class_name in class_names]  # Convert from tuple to list
        quiz_info = {
            "quiz_id": quiz.quiz_id,
            "title": quiz.title,
            "due_date": quiz.due_date,
            "time_limit": quiz.time_limit,
            "question_count": quiz.question_count,
            "class_ids": class_names_list 
        }
        quiz_list.append(quiz_info)
    # Return paginated quiz list
    return paginate(quiz_list, params)
#APi create Quiz
@router.post("/api/post/quizzes-with-questions", tags=["Quizzes"])
def create_quiz_with_questions(
    quiz_data: QuizWithQuestionsCreate,  # Dữ liệu chứa thông tin quiz và danh sách câu hỏi
    db: Session = Depends(get_db),
    current_user: Teacher = Depends(get_current_user)
):
    # Kiểm tra nếu người dùng hiện tại là giáo viên
    if not isinstance(current_user, Teacher):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ giáo viên mới có quyền tạo quiz.")
    # Tạo một quiz mới
    new_quiz = Quiz(
        title=quiz_data.title,
        due_date=quiz_data.due_date,
        time_limit=quiz_data.time_limit,
        question_count=quiz_data.question_count,  # Số lượng câu hỏi
        teacher_id=current_user.teacher_id
    )
    db.add(new_quiz)
    db.commit()
    db.refresh(new_quiz)
    # Phân công quiz cho từng lớp đã chỉ định và tạo thông báo cho học sinh
    for assignment in quiz_data.class_assignments:
        class_obj = db.query(Class).filter(Class.class_id == assignment.class_id).first()
        if not class_obj:
            raise HTTPException(status_code=404, detail=f"Lớp với ID {assignment.class_id} không tồn tại.")
        # Tạo bản phân công quiz cho lớp
        new_class_quiz = Class_quiz(
            class_quiz_id=str(uuid.uuid4()), 
            class_id=assignment.class_id,
            quiz_id=new_quiz.quiz_id
        )
        db.add(new_class_quiz)
        # Lấy danh sách học sinh trong lớp và tạo thông báo cho từng học sinh
        students = db.query(Student).filter(Student.class_id == assignment.class_id).all()
        for student in students:
            notification = Notification(
                noti_id=str(uuid.uuid4()),
                context=f"Một quiz mới '{new_quiz.title}' đã được giao và hạn nộp vào {new_quiz.due_date}.",
                time=datetime.now(),
                student_id=student.student_id
            )
            db.add(notification)
    # Tạo danh sách câu hỏi và câu trả lời
    for question_data in quiz_data.questions:
        new_question = Questions(
            quiz_id=new_quiz.quiz_id,
            question_text=question_data.question_text
        )
        db.add(new_question)
        db.commit()
        db.refresh(new_question)
        # Kiểm tra số lượng câu trả lời đúng
        correct_answers = [ans for ans in question_data.answers if ans.is_correct]
        if len(correct_answers) != 1:
            raise HTTPException(status_code=400, detail="Mỗi câu hỏi phải có đúng một câu trả lời chính xác.")
        # Thêm câu trả lời
        for answer_data in question_data.answers:
            new_answer = Answer(
                question_id=new_question.question_id,
                answer=answer_data.answer,
                is_correct=answer_data.is_correct
            )
            db.add(new_answer)
    db.commit()
    return {
        "message": "Quiz và các câu hỏi đã được tạo thành công.",
        "quiz_id": new_quiz.quiz_id,
    }

#Update lại
@router.put("/api/put/quizzes/{quiz_id}", tags=["Quizzes"])
def update_question_for_quiz(
    quiz_id: str,
    update_data: UpdateQuestion,
    db: Session = Depends(get_db),
    current_user: Teacher = Depends(get_current_user)
):
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id, Quiz.teacher_id == current_user.teacher_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Không tìm thấy quiz hoặc bạn không sở hữu quiz này")

    for question_data in update_data.question:
        # Tìm câu hỏi tương ứng
        question_info = db.query(Questions).filter(
            Questions.question_id == question_data.question_id,
            Questions.quiz_id == quiz_id  # Giữ quiz_id cố định
        ).first()
        if not question_info:
            raise HTTPException(status_code=404, detail=f"Câu hỏi {question_data.question_id} không tồn tại.")
        
        # Cập nhật các trường không phải khóa ngoại
        if question_data.question_text:
            question_info.question_text = question_data.question_text
        
        # Kiểm tra và cập nhật câu trả lời
        correct_answers = [ans for ans in question_data.answers if ans.is_correct]
        if len(correct_answers) != 1:
            raise HTTPException(status_code=400, detail=f"Câu hỏi {question_data.question_id} phải có đúng một câu trả lời chính xác.")

        # Cập nhật hoặc thêm câu trả lời mới
        for answer_data in question_data.answers:
            existing_answer = db.query(Answer).filter(
                Answer.question_id == question_data.question_id,
                Answer.answer_id == answer_data.answer_id  # Kiểm tra theo answer_id
            ).first()

            if existing_answer:
                # Nếu câu trả lời đã tồn tại, chỉ cần cập nhật
                existing_answer.answer = answer_data.answer
                existing_answer.is_correct = answer_data.is_correct
            else:
                # Nếu không tồn tại, thêm câu trả lời mới
                new_answer = Answer(
                    question_id=question_data.question_id,  # Không thay đổi question_id
                    answer=answer_data.answer,
                    is_correct=answer_data.is_correct
                )
                db.add(new_answer)

    db.commit()

    return {
        "message": "Cập nhật câu hỏi và câu trả lời thành công"
    }
    
#API lấy thông tin chi tiết về các question
@router.get("/api/quiz/{quiz_id}", response_model=QuizDetailResponse, tags=["Quizzes"])
def get_quiz_details(quiz_id: str, db: Session = Depends(get_db), current_user: Teacher = Depends(get_current_user)):
    # Lấy thông tin quiz
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id, Quiz.teacher_id == current_user.teacher_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Không tìm thấy quiz hoặc bạn không sở hữu quiz này")
    # Lấy các câu hỏi thuộc về quiz
    questions = db.query(Questions).filter(Questions.quiz_id == quiz_id).all()
    # Tạo danh sách câu hỏi và câu trả lời tương ứng
    question_responses = []
    for question in questions:
        answers = db.query(Answer).filter(Answer.question_id == question.question_id).all()
        answer_responses = [
            AnswerResponse(
                answer_id=answer.answer_id,
                answer=answer.answer,
                is_correct=answer.is_correct
            )
            for answer in answers
        ]
        question_responses.append(QuestionResponse(
            question_id=question.question_id,
            question_text=question.question_text,
            answers=answer_responses
        ))

    # Tạo và trả về thông tin quiz chi tiết
    return QuizDetailResponse(
        quiz_id=quiz.quiz_id,
        title=quiz.title,  # Giả định có trường title trong Quiz
        questions=question_responses
    )


@router.post("/api/quiz/doquiz", tags=["Quizzes"])
def do_quiz(
    request: QuizRequest,
    current_user: Student = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz_id = request.quiz_id  # Lấy quiz_id từ payload
    # Kiểm tra xem học sinh đã tham gia quiz này chưa
    class_quiz = db.query(Class_quiz).join(Class).filter(
        Class.class_id == current_user.class_id, Class_quiz.quiz_id == quiz_id
    ).first()
    if not class_quiz:
        raise HTTPException(status_code=403, detail="Student not enrolled in this quiz")
    # Kiểm tra nếu học sinh đã bắt đầu làm quiz (status là 'Continues')
    ongoing_quiz = db.query(Score).filter(
        Score.student_id == current_user.student_id,
        Score.quiz_id == quiz_id,
        Score.status == "Continues",
    ).first()
    if ongoing_quiz:
        # Tính toán thời gian còn lại
        remaining_time = ongoing_quiz.time_end - datetime.now()
        if remaining_time.total_seconds() <= 0:
            remaining_time = timedelta(seconds=0)  # Nếu hết thời gian
        return {
            "message": "Quiz is ongoing",
            "remaining_time": str(remaining_time),  # Trả về thời gian còn lại
        }
    # Nếu chưa bắt đầu làm bài, tạo mới bản ghi trong bảng Score
    quizes = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    new_doquiz = Score(
        score_id=str(uuid.uuid4()),
        student_id=current_user.student_id,
        quiz_id=quiz_id,
        time_start=datetime.now(),
        time_end=datetime.now() + timedelta(minutes=quizes.time_limit),
        status="Continues",
    )
    db.add(new_doquiz)
    db.commit()
    return {
        "message": "Quiz has started",
        "time_start": new_doquiz.time_start,
        "time_end": new_doquiz.time_end.strftime('%Y-%m-%d %H:%M:%S'),  # Thời gian kết thúc
    }

@router.post("/api/quiz/submit", tags=["Quizzes"])
def submit_quiz(
    quiz_data: QuizSubmission,
    current_user: Student = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Kiểm tra xem học sinh có tham gia quiz này không
    class_quiz = db.query(Class_quiz).join(Class).filter(
        Class.class_id == current_user.class_id, Class_quiz.quiz_id == quiz_data.quiz_id
    ).first()
    if not class_quiz:
        raise HTTPException(status_code=403, detail="Student not enrolled in this quiz")
    # Kiểm tra xem bài quiz đã được bắt đầu hay chưa
    ongoing_quiz = db.query(Score).filter(
        Score.student_id == current_user.student_id,
        Score.quiz_id == quiz_data.quiz_id,
        Score.status == "Continues",
    ).first()
    if not ongoing_quiz:
        raise HTTPException(status_code=400, detail="Quiz not started or already submitted")
    # Lưu đáp án của học sinh
    for answer in quiz_data.answers:
        new_choice = Choice(
            choice_id=str(uuid.uuid4()),
            answer_id=answer.answer_id,
            student_id=current_user.student_id,
        )
        db.add(new_choice)
    # Tính điểm
    correct_answers = db.query(Answer.answer_id).join(Questions).filter(
        Questions.quiz_id == quiz_data.quiz_id, Answer.is_correct == True
    ).all()
    correct_answer_ids = {ans.answer_id for ans in correct_answers}
    student_answer_ids = {answer.answer_id for answer in quiz_data.answers}
    correct_count = len(correct_answer_ids.intersection(student_answer_ids))
    total_questions = db.query(Questions).filter(Questions.quiz_id == quiz_data.quiz_id).count()
    score = (correct_count / total_questions) * 10 if total_questions > 0 else 0
    # Cập nhật trạng thái và điểm của học sinh trong bài quiz
    ongoing_quiz.status = "Completed"
    ongoing_quiz.score = score
    db.commit()
    return {
        "message": "Quiz submitted successfully",
        "score": score,
    }
    
@router.get("/api/quiz/{quiz_id}/review", response_model=QuizReviewResponse, tags=["Quizzes"])
def review_quiz(
    quiz_id: str,
    current_user: Student = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check if the quiz exists
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    student_score = db.query(Score).filter(
        Score.student_id == current_user.student_id, Score.quiz_id == quiz_id
    ).first()
    if not student_score:
        raise HTTPException(status_code=403, detail="No record of this quiz for the student")
    questions = db.query(Questions).filter(Questions.quiz_id == quiz_id).all()
    student_choices = db.query(Choice.answer_id, Answer.question_id).join(Answer).filter(
        Choice.student_id == current_user.student_id,
        Answer.question_id.in_([q.question_id for q in questions])
    ).all()
    student_answer_map = {choice.question_id: choice.answer_id for choice in student_choices}
    questions_review = []
    for question in questions:
        correct_answer = db.query(Answer).filter(
            Answer.question_id == question.question_id,
            Answer.is_correct == True
        ).first()
        student_answer_id = student_answer_map.get(question.question_id)
        student_answer = db.query(Answer).filter(
            Answer.answer_id == student_answer_id
        ).first() if student_answer_id else None 
        is_correct = student_answer_id == correct_answer.answer_id if student_answer else False
        questions_review.append(QuestionReview(
            question_id=question.question_id,
            question_text=question.question_text,
            student_answer=student_answer.answer if student_answer else None,
            correct_answer=correct_answer.answer,
            correct=is_correct
        ))
    return QuizReviewResponse(
        quiz_id=quiz.quiz_id,
        title=quiz.title,
        score=student_score.score,
        questions=questions_review
    )

#API lấy thông tin chi tiết về các question
@router.get("/api/quiz1/{quiz_id}", response_model=QuizDetailResponse1, tags=["Students"])
def get_quiz_details(quiz_id: str, db: Session = Depends(get_db)):
    # Lấy thông tin quiz
    quiz = db.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
    # Lấy các câu hỏi thuộc về quiz
    questions = db.query(Questions).filter(Questions.quiz_id == quiz_id).all()
    # Tạo danh sách câu hỏi và câu trả lời tương ứng
    question_responses = []
    for question in questions:
        answers = db.query(Answer).filter(Answer.question_id == question.question_id).all()
        answer_responses = [
            AnswerResponse1(
                answer_id=answer.answer_id,
                answer=answer.answer,

            )
            for answer in answers
        ]
        question_responses.append(QuestionResponse1(
            question_id=question.question_id,
            question_text=question.question_text,
            answers=answer_responses
        ))
    # Tạo và trả về thông tin quiz chi tiết
    return QuizDetailResponse1(
        quiz_id=quiz.quiz_id,
        title=quiz.title, 
        time_limit= quiz.time_limit,
        due_date= quiz.due_date,
        questions=question_responses
    )

@router.get("/api/teacher/quizzes/score", response_model=List[QuizSummaryResponse], tags=["Quizzes"])
def get_quizzes_by_teacher(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: Teacher = Depends(get_current_user)
):
    if not isinstance(current_user, Teacher):
        raise HTTPException(status_code=403, detail="Only teachers can access this endpoint.")
    quiz_summaries = (
        db.query(
            Quiz.quiz_id,
            Quiz.title,
            Quiz.due_date,
            func.count(case((Score.status == "Completed", Score.student_id), else_=None)).label("students_with_scores"),
            func.count(Student.student_id).label("total_student"),
            func.avg(Score.score).label("average_score")
        )
        .join(Class_quiz, Class_quiz.quiz_id == Quiz.quiz_id)
        .join(Student, Student.class_id == Class_quiz.class_id)
        .outerjoin(Score, (Score.quiz_id == Quiz.quiz_id) & (Score.student_id == Student.student_id))
        .filter(Quiz.teacher_id == current_user.teacher_id)  # Filter by current teacher
        .filter(Class_quiz.class_id == class_id)  # Filter by specific class_id
        .group_by(Quiz.quiz_id)
        .all()
    )
    return [
        QuizSummaryResponse(
            quiz_id=quiz.quiz_id,
            title=quiz.title,
            students_with_scores=quiz.students_with_scores,
            due_date = quiz.due_date,
            total_student=quiz.total_student,
            average_score=round(quiz.average_score, 2) if quiz.average_score is not None else 0.0,
            status=(
                "Completed"
                if quiz.students_with_scores == quiz.total_student
                else ("Ongoing" if quiz.due_date > datetime.now() else "Expired")
            )
        )
        for quiz in quiz_summaries
    ]




