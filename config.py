import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=".venv/.env")  # Tải các biến môi trường từ file .env

SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
AVATAR_UPLOAD_PATH = os.getenv("AVATAR_UPLOAD_PATH")
imageprofile = os.getenv("imageprofile")
DATABASE_URL = os.getenv("DATABASE_URL")
SMTP_SERVER= os.getenv("SMTP_SERVER")
SMTP_PORT= int(os.getenv("SMTP_PORT"))
SMTP_USER= os.getenv("SMTP_USER")
SMTP_PASS= os.getenv("SMTP_PASS")
Client_id = os.getenv("Client_id")

