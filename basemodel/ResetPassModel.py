from typing import List, Optional
from pydantic import BaseModel, EmailStr
from datetime import datetime

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

# Model Pydantic để đặt lại mật khẩu
class ResetPasswordRequest(BaseModel):
    email: str
    reset_code: str
    new_password: str
    confirm_password: str
