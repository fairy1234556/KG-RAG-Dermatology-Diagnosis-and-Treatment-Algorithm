from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


MethodName = Literal[
    "llm",
    "rag",
    "kg_rag",
]


DEFAULT_DISCLAIMER = (
    "本结果仅用于健康信息参考和辅助决策，"
    "不构成医学诊断，也不能替代医生面诊、"
    "皮肤镜检查或组织病理检查。"
)


class EvidencePath(BaseModel):
    """一条可追溯的医学证据路径。"""

    head_entity: str = Field(
        ...,
        description="头实体，例如基底细胞癌",
    )

    relation: str = Field(
        ...,
        description="关系，例如表现为",
    )

    tail_entity: str = Field(
        ...,
        description="尾实体，例如珍珠样结节",
    )

    evidence_text: str = Field(
        default="",
        description="支持该证据的原始文本",
    )

    source_id: str = Field(
        default="",
        description="证据来源编号",
    )

    source_name: str = Field(
        default="",
        description="证据来源名称",
    )

    score: Optional[float] = Field(
        default=None,
        description=(
            "路径或证据排序得分；"
            "纯 LLM 可为空"
        ),
    )


class TokenUsage(BaseModel):
    """单次大模型调用的 Token 使用情况。"""

    prompt_tokens: int = Field(
        default=0,
        ge=0,
    )

    completion_tokens: int = Field(
        default=0,
        ge=0,
    )

    total_tokens: int = Field(
        default=0,
        ge=0,
    )


class KGRAGResult(BaseModel):
    """
    三种实验方法统一使用的输出结构。

    适用方法：

    - llm：纯大模型基线；
    - rag：普通文本检索增强基线；
    - kg_rag：知识图谱增强方法。
    """

    case_id: str = Field(
        ...,
        description="测试样例编号",
    )

    method: MethodName = Field(
        ...,
        description="实验方法名称",
    )

    candidate_disease: str = Field(
        ...,
        description="待解释的候选疾病",
    )

    user_observation: str = Field(
        ...,
        description="用户输入的皮损观察文本",
    )

    observation_match: list[str] = Field(
        default_factory=list,
        description=(
            "用户观察与疾病证据之间的"
            "对应关系"
        ),
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
        description=(
            "可追溯证据路径；"
            "纯 LLM 和普通 RAG 可为空"
        ),
    )

    risk_warning: list[str] = Field(
        default_factory=list,
        description="需要关注的风险提示",
    )

    medical_advice: list[str] = Field(
        default_factory=list,
        description=(
            "非处方性的就医或检查建议"
        ),
    )

    evidence_gap: list[str] = Field(
        default_factory=list,
        description=(
            "当前证据不足、冲突或"
            "无法确认的部分"
        ),
    )

    sources: list[str] = Field(
        default_factory=list,
        description="本次回答使用的证据来源",
    )

    disclaimer: str = Field(
        default=DEFAULT_DISCLAIMER,
        description="医学免责声明",
    )

    model_name: str = Field(
        default="",
        description="调用的大模型名称",
    )

    prompt_version: str = Field(
        default="",
        description="提示词版本",
    )

    response_time_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="模型响应时间，单位毫秒",
    )

    token_usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="模型 Token 使用量",
    )

    run_status: Literal[
        "success",
        "failed",
    ] = Field(
        default="success",
        description="本次运行状态",
    )

    error_message: str = Field(
        default="",
        description="失败时记录的错误信息",
    )