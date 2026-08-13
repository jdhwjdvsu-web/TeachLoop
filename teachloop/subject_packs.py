from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml


ROOT = Path(__file__).parents[1]
SUBJECTS_ROOT = ROOT / "subjects"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError(f"学科包文件顶层必须是对象：{path}")
    return value


@lru_cache(maxsize=32)
def _load_validator(path: str) -> ModuleType:
    validator_path = Path(path)
    spec = importlib.util.spec_from_file_location(
        f"teachloop_subject_validator_{validator_path.parent.name}", validator_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载学科验证器：{validator_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=16)
def load_subject_pack(subject: str) -> dict[str, Any]:
    for directory in sorted(SUBJECTS_ROOT.iterdir() if SUBJECTS_ROOT.exists() else []):
        if not directory.is_dir():
            continue
        manifest = _read_yaml(directory / "manifest.yaml")
        if subject not in {manifest.get("name"), manifest.get("id")}:
            continue
        questions = _read_yaml(directory / "question_types.yaml")
        misconceptions = _read_yaml(directory / "misconceptions.yaml")
        rubrics = _read_yaml(directory / "rubrics.yaml")
        topics = questions.get("topics", {})
        return {
            **manifest,
            "directory": str(directory),
            "topics": topics,
            "misconceptions": misconceptions.get("misconceptions", {}),
            "rubrics": rubrics,
            "prompt": (directory / "prompts" / "system.md").read_text(
                encoding="utf-8"
            ),
        }
    raise KeyError(f"未找到学科包：{subject}")


@lru_cache(maxsize=1)
def list_subject_packs() -> list[dict[str, Any]]:
    packs: list[dict[str, Any]] = []
    for directory in sorted(SUBJECTS_ROOT.iterdir() if SUBJECTS_ROOT.exists() else []):
        if not directory.is_dir() or not (directory / "manifest.yaml").exists():
            continue
        manifest = _read_yaml(directory / "manifest.yaml")
        packs.append(load_subject_pack(str(manifest["name"])))
    order = {"数学": 0, "语文": 1, "物理": 2}
    return sorted(packs, key=lambda pack: order.get(str(pack.get("name")), 99))


def subject_names() -> list[str]:
    order = {"数学": 0, "语文": 1, "物理": 2}
    return sorted((pack["name"] for pack in list_subject_packs()), key=lambda x: order.get(x, 99))


def grades_for_subject(subject: str) -> list[str]:
    pack = load_subject_pack(subject)
    configured = {
        str(grade)
        for config in pack.get("topics", {}).values()
        for grade in config.get("grades", [])
    }
    declared = [str(grade) for grade in pack.get("grades", [])]
    supported = [grade for grade in declared if grade in configured]
    return supported or declared


def topics_for_subject(subject: str, grade: str | None = None) -> list[str]:
    pack = load_subject_pack(subject)
    items: list[str] = []
    for name, config in pack.get("topics", {}).items():
        grades = config.get("grades", pack.get("grades", []))
        if grade is None or grade in grades:
            items.append(str(name))
    return items


def infer_subject(topic: str) -> str:
    for pack in list_subject_packs():
        if topic in pack.get("topics", {}):
            return str(pack["name"])
    return "数学"


def topic_config(topic: str, subject: str | None = None) -> dict[str, Any]:
    resolved = subject or infer_subject(topic)
    pack = load_subject_pack(resolved)
    config = pack.get("topics", {}).get(topic)
    if config is None:
        first_topic = next(iter(pack.get("topics", {})), None)
        if first_topic is None:
            raise KeyError(f"学科包 {resolved} 没有配置课题")
        config = pack["topics"][first_topic]
    return config


def misconception_strategy(subject: str, name: str) -> str:
    pack = load_subject_pack(subject)
    item = pack.get("misconceptions", {}).get(name, {})
    if isinstance(item, str):
        return item
    return str(item.get("strategy", "使用示例、追问和即时反馈进行针对性教学。"))


def validate_subject_item(subject: str, topic: str, item: dict[str, Any]) -> bool:
    pack = load_subject_pack(subject)
    validator_path = Path(pack["directory"]) / "validators.py"
    module = _load_validator(str(validator_path))
    validator = getattr(module, "validate_item")
    return bool(validator(topic, item, topic_config(topic, subject)))


def pack_summary(subject: str, topic: str) -> dict[str, Any]:
    pack = load_subject_pack(subject)
    return {
        "id": pack["id"],
        "name": pack["name"],
        "version": str(pack.get("version", "1.0")),
        "topic": topic,
        "validator": pack.get("validator", "teacher_review"),
        "capability_skills": list(pack.get("capability_skills", [])),
        "status": pack.get("status", "试用"),
    }


def demo_path(subject: str, post_class: bool = False) -> Path:
    pack = load_subject_pack(subject)
    key = "post_class" if post_class else "pre_class"
    relative = pack.get("demo_data", {}).get(key)
    if not relative:
        relative = "data/demo_post_class.csv" if post_class else "data/demo_class.csv"
    return ROOT / str(relative)
