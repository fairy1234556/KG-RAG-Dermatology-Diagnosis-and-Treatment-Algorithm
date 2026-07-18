from __future__ import annotations

from fastapi import APIRouter

from backend.app.schemas.common import AppError, ok
from backend.app.schemas.knowledge_graph import EvidenceContextRequest
from backend.app.schemas.kg_rag import PromptRequest, TemplateGenerationRequest
from backend.app.services.evidence_context_service import EvidenceContextService
from backend.app.services.prompt_service import PromptService
from backend.app.services.template_generation_service import TemplateGenerationService

router = APIRouter(tags=["kg-rag"])


@router.post("/kg-rag/evidence-context")
def evidence_context(request: EvidenceContextRequest):
    context = EvidenceContextService().build(request.candidate_disease)
    return ok(context.model_dump())


@router.post("/kg-rag/prompts")
def kg_rag_prompt(request: PromptRequest):
    prompt = PromptService().build_prompt(
        candidate_disease=request.candidate_disease,
        user_observation=request.user_observation,
        prompt_version=request.prompt_version,
    )
    return ok(prompt.model_dump())


@router.post("/kg-rag/template-generations")
def template_generation(request: TemplateGenerationRequest):
    result = TemplateGenerationService().generate(
        candidate_disease=request.candidate_disease,
        user_observation=request.user_observation,
    )
    return ok(result.model_dump())


@router.post("/cases/{case_id}/analysis-runs")
def analysis_runs_placeholder(case_id: str):
    raise AppError(
        "NOT_IMPLEMENTED",
        (
            "analysis-runs is reserved for stage 3 orchestration. "
            "Stage 1 does not create cases, candidate ranking, or automatic validation results."
        ),
        status_code=501,
    )
