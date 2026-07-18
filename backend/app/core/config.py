from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the stage-1 backend."""

    app_name: str = "Dermatology KG-RAG Assistant API"
    system_version: str = "v1.0-stage1"
    kg_expected_entities: int = 70
    kg_expected_triples: int = 102
    kg_expected_sources: int = 25
    kg_expected_diseases: int = 7
    repo_root: Path = Path(__file__).resolve().parents[3]

    @property
    def kg_csv_dir(self) -> Path:
        configured = os.getenv("KG_CSV_DIR")
        if configured:
            path = Path(configured).expanduser()
            if not path.is_absolute():
                path = self.repo_root / path
            return path.resolve()
        return self.repo_root / "kg" / "csv"

    @property
    def kg_query_demo_path(self) -> Path:
        return self.repo_root / "kg" / "kg_query_demo.py"


settings = Settings()
