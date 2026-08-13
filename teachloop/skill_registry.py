from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).parents[1]
CATALOG_PATH = ROOT / "education_skills" / "catalog.yaml"


@lru_cache(maxsize=1)
def selected_skills() -> list[dict[str, Any]]:
    payload = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8")) or {}
    return list(payload.get("skills", []))


def skills_for_stage(stage: str, subject: str | None = None) -> list[dict[str, Any]]:
    matched = []
    for skill in selected_skills():
        stages = skill.get("stages", [])
        subjects = skill.get("subjects", ["通用"])
        if stage in stages and ("通用" in subjects or subject in subjects):
            matched.append(skill)
    return matched


def orchestration_manifest(subject: str) -> dict[str, Any]:
    stages = ("diagnosis", "planning", "assessment", "feedback")
    return {
        "library": "GarethManning/education-agent-skills",
        "license": "CC BY-SA 4.0",
        "mode": "selected-metadata-and-orchestration-reference",
        "stages": {
            stage: [skill["id"] for skill in skills_for_stage(stage, subject)]
            for stage in stages
        },
    }

