from collections.abc import Callable, Iterable
from .models import FactoryJob, JobStatus, PlanStep
Planner=Callable[[FactoryJob], list[PlanStep]]
ArtifactCollector=Callable[[FactoryJob], Iterable[str]]
class FactoryOrchestrator:
    def __init__(self, planner: Planner, artifact_collector: ArtifactCollector|None=None): self.planner=planner; self.artifact_collector=artifact_collector
    def run(self, job: FactoryJob)->FactoryJob:
        try:
            job.status=JobStatus.PLANNING
            plan=self.planner(job); job.metadata['plan']=[s.__dict__ for s in plan]; job.status=JobStatus.BUILDING
            if self.artifact_collector:
                for artifact in self.artifact_collector(job):
                    value=str(artifact)
                    if value and value not in job.artifacts: job.artifacts.append(value)
            return job
        except Exception as exc:
            job.status=JobStatus.FAILED; job.errors.append(str(exc)); return job
