from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from database import Base
import datetime


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    s_no = Column(Integer, unique=True, index=True)  # source dataset's own row ID — used as the matching key
    name = Column(String)
    email = Column(String, index=True)
    college = Column(String)
    branch = Column(String)
    cgpa = Column(Float)
    best_ai_project = Column(Text)
    research_work = Column(Text, nullable=True)
    github_profile = Column(String, nullable=True)
    resume_link = Column(String)
    resume_text = Column(Text, nullable=True)

    jd_score = Column(Float, nullable=True)
    github_score = Column(Float, nullable=True)
    github_details = Column(Text, nullable=True)

    test_la_score = Column(Float, nullable=True)
    test_code_score = Column(Float, nullable=True)

    final_score = Column(Float, nullable=True)
    status = Column(String, default="uploaded")
    # uploaded -> evaluated -> shortlisted -> tested -> interview_scheduled

    explanation = Column(Text, nullable=True)
    interview_time = Column(String, nullable=True)
    meet_link = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
