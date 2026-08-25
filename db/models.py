from sqlalchemy import Column, String, Text, Integer, DateTime, Boolean, JSON, BigInteger, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from db.base import Base
from sqlalchemy.sql import func


class Run(Base):
    __tablename__ = 'runs'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, nullable=False, unique=True)
    run_type = Column(String, nullable=False)  # 'eval' | 'single' | 'smoke'
    failure_mode_tag = Column(String)
    agent_name = Column(String, nullable=False)
    fixture_path = Column(String, nullable=False)
    perturbation_id = Column(UUID(as_uuid=True), ForeignKey('perturbations.id'))
    status = Column(String, nullable=False, default='pending')
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    created_at = Column(DateTime(timezone=True), nullable=False)

class Perturbation:
    __tablename__ = 'perturbations'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(String, nullable=False, ForeignKey('runs.run_id'))
    failure_mode_id = Column(String, nullable=False, ForeignKey('failure_modes.id'))
    perturbation_fn = Column(String, nullable=False)
    args_applied = Column(JSON, nullable=False, default=dict)
    applied_at = Column(DateTime(timezone=True), nullable=False)

class FailureMode(Base):
    __tablename__ = 'failure_modes'
    id = Column(String, primary_key=True)
    description = Column(Text, nullable=False)
    agent_name = Column(String, nullable=False)
    perturbation_fn = Column(String, nullable=False)
    perturbation_args = Column(JSON, nullable=False, default=dict)
    fixture_path = Column(String, nullable=False)
    expected_perturbed = Column(JSON, nullable=False)
    expected_control = Column(JSON, nullable=False)
    realism_bar = Column(String)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
