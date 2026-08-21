from __future__ import annotations

import os
import uuid
from pathlib import Path
from .ai_factory import FactoryJob, FactoryOrchestrator, baseline_plan, JobStatus

ROOT = Path(__file__).resolve().parent.parent


def collect_video_artifacts(job: FactoryJob):
    output = ROOT / 'output' / 'kids_animation' / 'kids-animation.mp4'
    if output.exists() and output.stat().st_size > 0:
        yield str(output)


def run(goal: str | None = None) -> FactoryJob:
    goal = goal or os.getenv('VIDEO_GOAL', 'Create a high-quality original kids poem/story animation with safe visuals, narration and YouTube-ready output.')
    job = FactoryJob(goal=goal, job_id=uuid.uuid4().hex[:12])
    result = FactoryOrchestrator(baseline_plan, collect_video_artifacts).run(job)
    result.metadata['video_entrypoint'] = 'src/kids_animation_production.py'
    result.metadata['zero_cost_mode'] = True
    return result


if __name__ == '__main__':
    job = run()
    print(f'FACTORY_JOB {job.job_id} {job.status.value}')
    if job.errors:
        print('ERRORS:', *job.errors, sep='\n')
    raise SystemExit(0 if job.status != JobStatus.FAILED else 1)
