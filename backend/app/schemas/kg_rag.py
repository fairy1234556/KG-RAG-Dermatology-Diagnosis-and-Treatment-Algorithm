from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class PromptRequest(BaseModel):
    candidate_disease: str
    user_observation: str
    prompt_version: Optional[str] = "doctor_kg_rag_v1"


class PromptResponse(BaseModel):
    prompt_text: str
    candidate_disease: str
    evidence_summary: Dict[str, Any]
    prompt_version: str
    safety_constraints: List[str]


class TemplateGenerationRequest(BaseModel):
    candidate_disease: str
    user_observation: str


class TemplateGenerationResponse(BaseModel):
    candidate_disease: str
    observation_evidence_matches: List[Dict[str, str]]
    supporting_evidence: List[Dict[str, str]]
    differential_diagnosis: List[Dict[str, str]]
    risk_warnings: List[Dict[str, str]]
    medical_advice_or_exams: List[Dict[str, str]]
    insufficient_evidence: List[str]
    disclaimer: str
    generation_mode: str = "template"

