"""
Common utilities shared by LLM, RAG and KG-RAG experiments.

Responsibilities:

1. Define the unified medical explanation prompt.
2. Parse JSON returned by the LLM.
3. Validate output with KGRAGResult.
4. Inject experiment metadata such as model name, token usage and latency.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from pydantic import ValidationError

from rag.llm_client import LLMResult
from rag.schemas import KGRAGResult
from rag.schemas import MethodName
from rag.schemas import TokenUsage


BASELINE_SYSTEM_PROMPT = """
你是一名皮肤病医学知识辅助解释助手。

你的任务是根据给定的候选疾病、用户观察结果，以及可能提供的外部证据，
生成谨慎、可追溯、结构化的辅助解释。

必须遵守以下规则：

1. 本回答仅用于健康信息参考，不构成医学诊断。
2. 不得把候选疾病描述为已经确诊。
3. 不得编造用户未提供的症状、部位、检查结果或病史。
4. 只有在输入中提供了外部证据时，才能将其表述为引用证据。
5. 证据不足时必须明确写入 evidence_gap。
6. 不得提供处方药名称、药物剂量或自行治疗方案。
7. medical_advice 只能包含就医、观察记录和检查建议。
8. 必须返回一个合法 JSON 对象，不能输出 Markdown 代码块或额外说明。
""".strip()


OUTPUT_JSON_INSTRUCTION = """
请严格返回以下 JSON 结构：

{
  "observation_match": [
    "用户观察与候选疾病之间可以确认的对应关系"
  ],
  "supporting_evidence": [
    "支持候选疾病的医学证据"
  ],
  "differential_diagnosis": [
    "需要鉴别的其他疾病或病变"
  ],
  "risk_warning": [
    "需要关注的风险提示"
  ],
  "medical_advice": [
    "非处方性的就医或检查建议"
  ],
  "evidence_gap": [
    "当前缺少、冲突或无法确认的信息"
  ],
  "sources": [
    "本次回答实际使用的证据来源"
  ]
}

字段要求：

- 所有字段都必须存在。
- 所有字段的值必须是字符串数组。
- 没有相应内容时返回空数组。
- 不得增加未定义字段。
- 不得输出 JSON 之外的文字。
""".strip()


C3_OUTPUT_JSON_INSTRUCTION = """
请严格返回以下 JSON 结构，保留所有字段，不输出 JSON 之外的文字：
{
  "observation_match": [],
  "supporting_evidence": [],
  "differential_diagnosis": [],
  "risk_warning": [],
  "medical_advice": [],
  "evidence_gap": [],
  "sources": [],
  "claims": [
    {
      "claim_id": "CLAIM_001",
      "claim_text": "一条基于输入证据的解释",
      "patient_fact_ids": [],
      "kg_path_ids": []
    }
  ]
}

- 原有七个字段仍为字符串数组；无相应内容时返回空数组。
- claims 为逐条解释对象数组，每项只含示例中的四个字段。
- claim_id 使用 CLAIM_001、CLAIM_002 等本次回答内唯一的非空编号；claim_text 为非空字符串。
- patient_fact_ids、kg_path_ids 必须为字符串数组，只能引用输入 C2 结构化证据台账中
  patient_facts 的 fact_id 和 paths 的 path_id，不得编造编号或使用 entity_id、triple_id 替代。
- 没有引用某类证据时对应数组为空；如果没有 KG 路径，kg_path_ids 必须为 []，不得虚构路径编号。
- 不得编造患者症状、检查结果或病史。患者事实状态以 C2 台账的 fact_state 为准：
  present：患者明确存在该表现，应表述为“存在”“伴有”等。
  absent：患者明确不存在该表现，应表述为“明确否认”“未见”等，不能写成“未提及”“未知”。
  missing：患者没有提供该信息，应表述为“未提供”“未知”等，不能写成“没有”“未见”。
  absent、missing 只能分别用于说明否认或信息缺口，不能作为阳性支持，missing 不等于 absent。
- claims 中每个涉及患者具体表现的陈述，都必须对应 C2 patient_facts 中已登记的事实，
  并在该条解释的 patient_fact_ids 中列出所涉及的全部 fact_id；否认或信息缺口的陈述也不例外。
  引用 absent 事实时同样必须填写对应的 patient_fact_ids，不能因其不属于阳性匹配而省略引用。
- 即使原始观察包含某个表现，只要 C2 未登记对应患者事实，就不要将该表现写入 claims 的患者陈述；
  不得为未登记的事实自行编造 fact_id，也不得借用其他事实的编号代替。
- 只有 present 且 mapping_reliable=true，并与路径 matched_fact_ids 对应的事实，
  才能结合 PATIENT_SUPPORT 路径说明患者匹配支持；非精确映射不能作为可靠阳性匹配。
- BACKGROUND_ONLY 只能描述 KG 背景知识，不能描述成患者已经出现的表现。
- DIFFERENTIAL_ONLY 只能用于鉴别说明，不能当作候选疾病的直接支持。
- BACKGROUND_ONLY 和 DIFFERENTIAL_ONLY 均不能作为候选疾病的患者级直接支持。
- 证据不足时应在解释及 evidence_gap 中明确说明，不得强行支持候选疾病；
  没有可用证据时可生成说明证据不足的解释，引用数组为空，不要照抄示例占位文字。
- 事实与知识相符不代表确诊，不能把候选疾病解释成已经确诊。
""".strip()


class BaselineOutputError(RuntimeError):
    """统一 Baseline 输出处理异常。"""


def build_user_prompt(
    candidate_disease: str,
    user_observation: str,
    method_description: str,
    evidence_context: str = "",
    *,
    include_claims: bool = False,
) -> str:
    """构造三种方法共用的用户提示词。"""

    disease = candidate_disease.strip()
    observation = user_observation.strip()
    method = method_description.strip()
    evidence = evidence_context.strip()

    if not disease:
        raise ValueError(
            "candidate_disease 不能为空。"
        )

    if not observation:
        raise ValueError(
            "user_observation 不能为空。"
        )

    sections = [
        "一、实验方法",
        method,
        "",
        "二、候选疾病",
        disease,
        "",
        "三、用户观察",
        observation,
    ]

    if evidence:
        sections.extend(
            [
                "",
                "四、允许使用的外部证据",
                evidence,
            ]
        )
    else:
        sections.extend(
            [
                "",
                "四、外部证据",
                "本方法不提供外部检索证据。",
            ]
        )

    sections.extend(
        [
            "",
            "五、输出要求",
            C3_OUTPUT_JSON_INSTRUCTION if include_claims else OUTPUT_JSON_INSTRUCTION,
        ]
    )

    return "\n".join(sections)


def strip_json_fence(text: str) -> str:
    """移除模型偶尔返回的 Markdown JSON 代码块。"""

    cleaned = (text or "").strip()

    fence_pattern = re.compile(
        r"^```(?:json)?\s*(.*?)\s*```$",
        flags=re.IGNORECASE | re.DOTALL,
    )

    match = fence_pattern.match(cleaned)

    if match:
        return match.group(1).strip()

    return cleaned


def extract_json_object(text: str) -> Dict[str, Any]:
    """从模型文本中解析 JSON 对象。"""

    cleaned = strip_json_fence(text)

    try:
        parsed = json.loads(cleaned)

    except json.JSONDecodeError:
        start_index = cleaned.find("{")
        end_index = cleaned.rfind("}")

        if (
            start_index == -1
            or end_index == -1
            or end_index <= start_index
        ):
            raise BaselineOutputError(
                "模型返回内容中没有可解析的 JSON 对象。"
            )

        json_text = cleaned[
            start_index : end_index + 1
        ]

        try:
            parsed = json.loads(json_text)

        except json.JSONDecodeError as exc:
            raise BaselineOutputError(
                "模型返回的 JSON 格式无效："
                f"{exc}"
            ) from exc

    if not isinstance(parsed, dict):
        raise BaselineOutputError(
            "模型返回值必须是 JSON 对象。"
        )

    return parsed


def normalize_string_list(
    value: Any,
    field_name: str,
) -> List[str]:
    """确保模型字段被转换为字符串列表。"""

    if value is None:
        return []

    if isinstance(value, str):
        cleaned = value.strip()
        return [cleaned] if cleaned else []

    if not isinstance(value, list):
        raise BaselineOutputError(
            f"{field_name} 必须是字符串数组。"
        )

    result: List[str] = []

    for item in value:
        if item is None:
            continue

        if not isinstance(item, str):
            raise BaselineOutputError(
                f"{field_name} 中包含非字符串内容。"
            )

        cleaned = item.strip()

        if cleaned and cleaned not in result:
            result.append(cleaned)

    return result


def normalize_model_payload(
    payload: Dict[str, Any],
) -> Dict[str, List[str]]:
    """清理并限制模型允许返回的医学内容字段。"""

    allowed_fields = [
        "observation_match",
        "supporting_evidence",
        "differential_diagnosis",
        "risk_warning",
        "medical_advice",
        "evidence_gap",
        "sources",
    ]

    return {
        field_name: normalize_string_list(
            payload.get(field_name, []),
            field_name,
        )
        for field_name in allowed_fields
    }


def build_structured_result(
    case_id: str,
    method: MethodName,
    candidate_disease: str,
    user_observation: str,
    llm_result: LLMResult,
    *,
    include_claims: bool = False,
) -> KGRAGResult:
    """解析模型输出并构造统一实验结果。"""

    payload = extract_json_object(
        llm_result.content
    )

    normalized_payload = normalize_model_payload(
        payload
    )

    result_data = {
        "case_id": case_id.strip(),
        "method": method,
        "candidate_disease": (
            candidate_disease.strip()
        ),
        "user_observation": (
            user_observation.strip()
        ),
        "observation_match": (
            normalized_payload[
                "observation_match"
            ]
        ),
        "supporting_evidence": (
            normalized_payload[
                "supporting_evidence"
            ]
        ),
        "differential_diagnosis": (
            normalized_payload[
                "differential_diagnosis"
            ]
        ),
        "risk_warning": (
            normalized_payload[
                "risk_warning"
            ]
        ),
        "medical_advice": (
            normalized_payload[
                "medical_advice"
            ]
        ),
        "evidence_gap": (
            normalized_payload[
                "evidence_gap"
            ]
        ),
        "sources": normalized_payload["sources"],
        "model_name": llm_result.model,
        "prompt_version": (
            llm_result.prompt_version
        ),
        "response_time_ms": int(
            round(
                llm_result.latency_seconds
                * 1000
            )
        ),
        "token_usage": TokenUsage(
            prompt_tokens=(
                llm_result.prompt_tokens
            ),
            completion_tokens=(
                llm_result.completion_tokens
            ),
            total_tokens=(
                llm_result.total_tokens
            ),
        ),
        "run_status": "success",
        "error_message": "",
    }

    # 旧调用默认忽略新增字段；C3 单独解析对象数组，不能用字符串数组归一化。
    # 兼容旧模型响应：未提供 claims 时保留空数组，不从旧文本猜测引用关系。
    if include_claims:
        result_data["claims"] = payload.get("claims", [])

    try:
        if hasattr(
            KGRAGResult,
            "model_validate",
        ):
            return KGRAGResult.model_validate(
                result_data
            )

        return KGRAGResult.parse_obj(
            result_data
        )

    except ValidationError as exc:
        raise BaselineOutputError(
            "模型输出无法通过统一结果结构校验："
            f"{exc}"
        ) from exc


def result_to_dict(
    result: KGRAGResult,
) -> Dict[str, Any]:
    """兼容 Pydantic V1 和 V2 的字典转换。"""

    if hasattr(result, "model_dump"):
        return result.model_dump()

    return result.dict()
