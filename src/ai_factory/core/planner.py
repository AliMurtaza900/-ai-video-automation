from .models import FactoryJob, PlanStep

def baseline_plan(job: FactoryJob) -> list[PlanStep]:
    return [
        PlanStep('specify', f'Turn the goal into a precise system specification: {job.goal}', 1, 'architect', outputs=['specification']),
        PlanStep('build', 'Generate the initial implementation from the specification.', 2, 'builder', ['specification'], ['implementation']),
        PlanStep('test', 'Run automated validation and record failures.', 3, 'tester', ['implementation'], ['test_report']),
        PlanStep('improve', 'Use test results to propose and apply targeted improvements.', 4, 'improver', ['implementation','test_report'], ['revised_implementation']),
    ]
