from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Optional

from backend.app.core.config import settings


class ResearchDemoAdapter:
    """File-based adapter for existing research demo scripts.

    The adapter avoids backend-side working-directory assumptions. It loads demo
    modules from their known files and leaves the original scripts unchanged.
    """

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        self.repo_root = repo_root or settings.repo_root

    @staticmethod
    def _load_module(module_name: str, path: Path) -> ModuleType:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module {module_name} from {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def load_kg_query_demo(self) -> ModuleType:
        return self._load_module(
            "stage1_kg_query_demo_adapter",
            self.repo_root / "kg" / "kg_query_demo.py",
        )

    def load_kg_evidence_context_demo(self) -> ModuleType:
        # kg_evidence_context_demo imports `kg_query_demo` by module name.
        # Register the already file-loaded module so the demo remains unchanged.
        sys.modules.setdefault("kg_query_demo", self.load_kg_query_demo())
        return self._load_module(
            "stage1_kg_evidence_context_demo_adapter",
            self.repo_root / "kg" / "kg_evidence_context_demo.py",
        )

    def build_prompt_v1(self, candidate_disease: str, user_observation: str) -> str:
        module = self._load_module(
            "stage1_kg_rag_prompt_demo_adapter",
            self.repo_root / "rag" / "kg_rag_prompt_demo.py",
        )
        return module.build_prompt(candidate_disease, user_observation)

    def build_prompt_v2(self, candidate_disease: str, user_observation: str) -> str:
        # kg_rag_prompt_demo_v2 imports `kg_evidence_context_demo` by module name.
        sys.modules.setdefault(
            "kg_evidence_context_demo", self.load_kg_evidence_context_demo()
        )
        module = self._load_module(
            "stage1_kg_rag_prompt_demo_v2_adapter",
            self.repo_root / "rag" / "kg_rag_prompt_demo_v2.py",
        )
        return module.build_kg_rag_prompt(candidate_disease, user_observation)

