"""Load and persist the application configuration (config/config.yaml).

Bot commands like /level and /time call `save_config` so changes survive
restarts, instead of only living in the SQLite `user_state` table.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

VALID_MODES = ("level_only", "level_and_below")


@dataclass
class StudyConfig:
    level: int = 1
    mode: str = "level_and_below"
    send_time: str = "08:00"
    timezone: str = "America/Costa_Rica"


@dataclass
class AppConfig:
    study: StudyConfig = field(default_factory=StudyConfig)
    db_path: str = "storage/library.db"
    log_level: str = "INFO"
    log_file: str = "storage/app.log"


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    study_raw = raw.get("study", {})
    study = StudyConfig(
        level=int(study_raw.get("level", 1)),
        mode=study_raw.get("mode", "level_and_below"),
        send_time=study_raw.get("send_time", "08:00"),
        timezone=study_raw.get("timezone", "America/Costa_Rica"),
    )
    if study.mode not in VALID_MODES:
        raise ValueError(f"Invalid study.mode in config.yaml: {study.mode!r}")

    db_raw = raw.get("database", {})
    log_raw = raw.get("logging", {})

    return AppConfig(
        study=study,
        db_path=db_raw.get("path", "storage/library.db"),
        log_level=log_raw.get("level", "INFO"),
        log_file=log_raw.get("file", "storage/app.log"),
    )


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    data = {
        "study": {
            "level": config.study.level,
            "mode": config.study.mode,
            "send_time": config.study.send_time,
            "timezone": config.study.timezone,
        },
        "database": {"path": config.db_path},
        "logging": {"level": config.log_level, "file": config.log_file},
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
