from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class JobStatus(str, Enum):
    PENDING='pending'; PLANNING='planning'; BUILDING='building'; TESTING='testing'; IMPROVING='improving'; DEPLOYING='deploying'; COMPLETED='completed'; FAILED='failed'

@dataclass
class FactoryJob:
    goal: str
    job_id: str
    status: JobStatus = JobStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

@dataclass
class PlanStep:
    name: str
    description: str
    order: int
    agent_role: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
