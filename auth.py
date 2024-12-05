from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from database import get_db
from models import Student, Teacher, Admin, Class, Subject
from pydantic import BaseModel
from passlib.context import CryptContext
from uuid import uuid4
import os
from typing import Optional, Union
import uuid
from config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, AVATAR_UPLOAD_PATH, SMTP_SERVER, SMTP_PASS, SMTP_PORT, SMTP_USER
from basemodel.AuthModel import TokenData, Token, ChangeRespone
from basemodel.ResetPassModel import ResetPasswordRequest
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import string
import random
import smtplib
import aiohttp


router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, role: str, subject_id:Optional[int] = None, class_id:Optional[int] = None, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "role": role, "subject_id": subject_id, "class_id":class_id })
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def send_email(to_email: str, reset_code: str):
    subject = "Mã xác nhận đặt lại mật khẩu"
    body = f"Xin chào, đây là mã xác nhận của bạn: {reset_code}"
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Không thể gửi email: {e}")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None or role is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, role=role)
    except JWTError:
        raise credentials_exception
    if token_data.role == "student":
        user = db.query(Student).filter(Student.student_id == token_data.user_id).first()
    elif token_data.role == "teacher":
        user = db.query(Teacher).filter(Teacher.teacher_id == token_data.user_id).first()
    elif token_data.role == "admin":
        user = db.query(Admin).filter(Admin.admin_id == token_data.user_id).first()
    else:
        raise credentials_exception
    if user is None:
        raise credentials_exception
    return user

@router.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Kiểm tra học sinh
    student = db.query(Student).filter(Student.mastudent == form_data.username).first()
    if student and verify_password(form_data.password, student.password):
        access_token = create_access_token(data={"sub": student.student_id}, role="student", class_id = student.class_id)
        return {"access_token": access_token, "token_type": "bearer", "role": "student", "first_login": student.first_login}
    # Kiểm tra giáo viên
    teacher = db.query(Teacher).filter(Teacher.mateacher == form_data.username).first()
    if teacher and verify_password(form_data.password, teacher.password):
        access_token = create_access_token(data={"sub": teacher.teacher_id}, role="teacher", subject_id = teacher.subject_id)
        return {"access_token": access_token, "token_type": "bearer", "role": "teacher"}
    # Kiểm tra quản trị viên
    admin = db.query(Admin).filter(Admin.admin_id == form_data.username).first()
    if admin and verify_password(form_data.password, admin.password):
        access_token = create_access_token(data={"sub": admin.admin_id}, role="admin")
        return {"access_token": access_token, "token_type": "bearer", "role": "admin"}
    # Nếu thông tin không đúng
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.post("/api/change-password")
def change_password(
    request: ChangeRespone,
    db: Session = Depends(get_db),
    current_user: Student = Depends(get_current_user)
):
    if not isinstance(current_user, (Student, Teacher)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ học sinh mới có thể thay đổi mật khẩu")
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu xác nhận không đúng")
    if current_user.first_login is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Người dùng này đã thay đổi mật khẩu rồi")
    current_user.password = hash_password(request.new_password)
    current_user.first_login = False
    db.commit()
    return {"message": "Đổi mật khẩu thành công"}

@router.get("/users/me")
def read_users_me(current_user: BaseModel = Depends(get_current_user), db: Session = Depends(get_db)):
    if isinstance(current_user, Student):
        classes = db.query(Class).filter(Class.class_id == current_user.class_id).first()
        return {"user_id": current_user.student_id, 
                "role": "student", 
                "mastudent": current_user.mastudent,
                "gender" :current_user.gender,
                "name" : current_user.name, 
                "birth_date" : current_user.birth_date, 
                "email" : current_user.email, 
                "phone_number": current_user.phone_number, 
                "image" : current_user.image, 
                "name_class" : classes.name_class,
                "first_login": current_user.first_login}
    elif isinstance(current_user, Teacher):
        subjects = db.query(Subject).filter(Subject.subject_id == current_user.subject_id).first()
        return {"user_id": current_user.teacher_id,
                "role": "teacher", 
                "mateacher": current_user.mateacher,
                "gender" :current_user.gender,
                "name" : current_user.name, 
                "birth_date" : current_user.birth_date, 
                "email" : current_user.email, 
                "phone_number": current_user.phone_number, 
                "image" : current_user.image, 
                "name_subject" : subjects.name_subject}
    elif isinstance(current_user, Admin):
        return {"user_id": current_user.admin_id, "role": "admin"}
    else:
        raise HTTPException(status_code=400, detail="Invalid user role")
        

#Upload avatar
# @router.post("/users/me/avatar")
# async def upload_avatar(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db),
#     current_user: BaseModel = Depends(get_current_user)
# ):
#     # Kiểm tra nếu người dùng là học sinh hoặc giáo viên
#     if not isinstance(current_user, (Student, Teacher)):
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ học sinh và giáo viên mới có thể thay đổi ảnh đại diện")
#     # Kiểm tra đuôi tệp ảnh
#     if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng ảnh không hợp lệ")
#     # Xóa ảnh cũ nếu tồn tại
#     if current_user.image:
#         old_file_path = os.path.join(AVATAR_UPLOAD_PATH, current_user.image)
#         if os.path.exists(old_file_path):
#             os.remove(old_file_path)
#     # Tạo tên tệp duy nhất và xác định đường dẫn lưu
#     file_extension = file.filename.split(".")[-1]
#     new_filename = f"{uuid4()}.{file_extension}"
#     file_path = os.path.join(AVATAR_UPLOAD_PATH, new_filename)
#     # Lưu tệp ảnh mới vào thư mục đích
#     with open(file_path, "wb") as buffer:
#         buffer.write(await file.read())
#     # Cập nhật đường dẫn ảnh vào cơ sở dữ liệu của người dùng
#     image_url = new_filename  # Đường dẫn lưu trữ
#     current_user.image = image_url
#     db.commit()
#     return {"message": "Tải lên ảnh thành công", "image_url": image_url}

async def upload_image_to_imgur(file: UploadFile):
    CLIENT_ID = CLIENT_ID1
    headers = {
        'Authorization': f'Client-ID {CLIENT_ID}'
    }
    # Đọc nội dung file ảnh
    image_data = await file.read()
    # Thực hiện upload ảnh lên imgur
    url = "https://api.imgur.com/3/image"
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data={'image': image_data}) as response:
            if response.status == 200:
                image_data = await response.json()
                return image_data['data']['link'], image_data['data']['id'], image_data['data']['deletehash']
            else:
                # Lấy thông tin lỗi chi tiết từ phản hồi
                error_message = await response.text()
                raise Exception(f"Lỗi khi tải ảnh lên imgur: {error_message}")

@router.post("/users/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Union[Student, Teacher] = Depends(get_current_user)
):
    # Kiểm tra nếu người dùng là học sinh hoặc giáo viên
    if not isinstance(current_user, (Student, Teacher)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ học sinh và giáo viên mới có thể thay đổi ảnh đại diện")
    
    # Kiểm tra đuôi tệp ảnh
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Định dạng ảnh không hợp lệ")
    
    # Upload ảnh lên imgur
    image_url, image_id, image_delete_hash = await upload_image_to_imgur(file)
    
    # Xóa ảnh cũ nếu tồn tại
    if current_user.image_delete_hash:
        # Thực hiện xóa ảnh cũ từ imgur nếu có
        delete_url = f"https://api.imgur.com/3/image/{current_user.image_delete_hash}"
        headers = {'Authorization': f'Client-ID YOUR_CLIENT_ID'}
        async with aiohttp.ClientSession() as session:
            async with session.delete(delete_url, headers=headers) as delete_response:
                if delete_response.status != 200:
                    error_message = await delete_response.text()
                    raise HTTPException(status_code=400, detail=f"Lỗi khi xóa ảnh cũ từ imgur: {error_message}")
    
    # Cập nhật URL ảnh và id ảnh vào cơ sở dữ liệu
    current_user.image = image_url
    current_user.image_id = image_id
    current_user.image_delete_hash = image_delete_hash
    db.commit()
    
    return {"message": "Tải lên ảnh thành công", "image_url": image_url, "image_id": image_id}

#Gửi mã xác nhận đặt lại mật khẩu
@router.post("/api/forgot_password")
def forgot_password(email: str, db: Session = Depends(get_db)):
    # Tìm email trong bảng Student và Teacher
    student = db.query(Student).filter(Student.email == email).first()
    teacher = db.query(Teacher).filter(Teacher.email == email).first()

    if not student and not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy email trong hệ thống.")
    # Xác định người dùng và lưu mã xác nhận
    user = student if student else teacher
    reset_code = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
    expiry_time = datetime.utcnow() + timedelta(minutes=10)

    user.reset_code = reset_code
    user.resetPasswordExpiry = expiry_time
    db.commit()
    # Gửi email mã xác nhận
    send_email(user.email, reset_code)
    return {"message": "Mã xác nhận đã được gửi tới email của bạn."}

# API đặt lại mật khẩu
@router.post("/api/reset_password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    # Tìm email trong bảng Student và Teacher
    student = db.query(Student).filter(Student.email == request.email).first()
    teacher = db.query(Teacher).filter(Teacher.email == request.email).first()

    if not student and not teacher:
        raise HTTPException(status_code=404, detail="Không tìm thấy email trong hệ thống.")
    # Xác định người dùng cần đặt lại mật khẩu
    user = student if student else teacher
    # Kiểm tra mã xác nhận và thời gian hết hạn
    if user.reset_code != request.reset_code:
        raise HTTPException(status_code=400, detail="Mã xác nhận không đúng.")
    if datetime.utcnow() > user.resetPasswordExpiry:
        raise HTTPException(status_code=400, detail="Mã xác nhận đã hết hạn.")
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Mật khẩu xác nhận không trùng khớp.")
    # Cập nhật mật khẩu mới và xóa mã xác nhận
    user.password = request.new_password  # Hash mật khẩu trước khi lưu nếu cần
    user.reset_code = None
    user.resetPasswordExpiry = None
    db.commit()

    return {"message": "Mật khẩu của bạn đã được đặt lại thành công."}
