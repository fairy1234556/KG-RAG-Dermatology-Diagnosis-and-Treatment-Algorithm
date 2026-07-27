from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


MethodName = Literal["llm", "rag", "kg_rag"]


class EvidencePath(BaseModel):
    """一条知识图谱证据路径。"""

    head_entity: str = Field(..., description="头实体，例如基底细胞癌")
    relation: str = Field(..., description="关系，例如表现为")
    tail_entity: str = Field(..., description="尾实体，例如珍珠样结节")
    evidence_text: str = Field(
        default="",
        description="支持该三元组的证据文本",
    )
    source_id: str = Field(
        default="",
        description="证据来源编号",
    )
    source_name: str = Field(
        default="",
        description="证据来源名称",
    )
    score: float | None = Field(
        default=None,
        description="路径排序得分，纯 LLM 和普通 RAG 可为空",
    )


class KGRAGResult(BaseModel):
    """三种实验方法统一使用的输出结构。"""

    case_id: str
    method: MethodName
    candidate_disease: str

    observation_match: list[str] = Field(
        default_factory=list,
        description="用户观察与证据匹配情况",
    )

    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="支持候选疾病的医学证据",
    )

    differential_diagnosis: list[str] = Field(
        default_factory=list,
        description="需要鉴别的疾病或病变",
    )

    evidence_paths: list[EvidencePath] = Field(
        default_factory=list,
        description="可追溯的证据路径",
    )

    risk_warning: list[str] = Field(
        default_factory=list,
        description="风险提示",
    )

    medical_advice: list[str] = Field(
        default_factory=list,
        description="非处方性的就医和检查建议",
    )

    evidence_gap: list[str] = Field(
        default_factory=list,
        description="证据不足或无法支持的部分",
    )

    sources: list[str] = Field(
        default_factory=list,
        description="引用的证据来源",
    )

    model_name: str = ""
    prompt_version: str = ""
    response_time_ms: int | None = None
    run_status: Literal["success", "failed"] = "success"
    error_message: str = ""