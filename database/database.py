import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client

load_dotenv()
POSTGRESS_URL = os.getenv("postgress_url")
engine = create_engine(
    POSTGRESS_URL,
    pool_pre_ping=True,     
    pool_recycle=300,        
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
        
SUPABASE_URL = os.getenv("SUPABASE_URL")           
SUPABASE_KEY = os.getenv("SUPABASE_KEY") 
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) 

from sqlalchemy import text

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        print("Connected! PostgreSQL version:", result.fetchone()[0])
except Exception as e:
    print("Connection failed:", e)