import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, DateTime, String, Text, create_engine
import shutil
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = Path("jobs.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="queued")
    options = Column(Text)
    input_path = Column(String)
    output_dir = Column(String)
    result_json = Column(Text, nullable=True)

    def options_dict(self):
        return json.loads(self.options or "{}")


Base.metadata.create_all(bind=engine)

def purge_old_jobs(session, cutoff_hours: int = 24):
    """Delete jobs older than cutoff and remove their files."""
    from datetime import timedelta

    cutoff = datetime.utcnow() - timedelta(hours=cutoff_hours)
    old_jobs = session.query(Job).filter(Job.created_at < cutoff).all()
    for job in old_jobs:
        if job.output_dir:
            shutil.rmtree(job.output_dir, ignore_errors=True)
        if job.input_path:
            try:
                Path(job.input_path).unlink()
            except FileNotFoundError:
                pass
        session.delete(job)
    session.commit()

