from __future__ import annotations


def improve_settings(report, settings: dict) -> dict:
    """Translate QC failures into safe renderer settings without paid AI calls."""
    updated = dict(settings)
    for issue in report.issues:
        if issue == "wrong_resolution":
            updated["WIDTH"], updated["HEIGHT"] = 1280, 720
        elif issue == "low_fps":
            updated["FPS"] = max(int(updated.get("FPS", 24)), 24)
        elif issue == "missing_audio":
            updated["REGENERATE_AUDIO"] = True
        elif issue in {"missing_or_tiny_video", "no_video_stream"}:
            updated["FORCE_FULL_RENDER"] = True
    updated["QUALITY_ATTEMPT"] = int(updated.get("QUALITY_ATTEMPT", 0)) + 1
    return updated
