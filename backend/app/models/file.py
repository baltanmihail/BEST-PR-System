"""
Модель файла
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from app.database import Base


class File(Base):
    """Файл (материалы задачи)"""
    __tablename__ = "files"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    drive_id = Column(String, nullable=False)  # Google Drive file ID
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False, index=True)  # 'script', 'video', 'image', 'document'
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    task = relationship("Task", foreign_keys=[task_id], backref="files_list")  # backref для обратной связи
    
    __table_args__ = (
        CheckConstraint("LENGTH(TRIM(file_name)) > 0", name="files_file_name_not_empty"),
    )
    
    def __repr__(self):
        return f"<File {self.file_name} (type: {self.file_type})>"
