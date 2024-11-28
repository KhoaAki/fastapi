from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

#DATABASE_URL = "mysql+pymysql://root:AIhcjdhXLpifMdBVWmNSMEzZbWVjlTfG@autorack.proxy.rlwy.net:53796/railway"
#DATABASE_URL = "mysql+pymysql://root:12345@localhost:3306/quiz2"
DATABASE_URL ="mysql+pymysql://root:DpSvDwSFzLYmvmqyhzcxLNtiirYZhYvh@autorack.proxy.rlwy.net:48224/quiz2"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
