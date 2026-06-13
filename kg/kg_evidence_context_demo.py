"""
Build structured LLM evidence context from the dermatology knowledge graph.

Run:
    python kg/kg_evidence_context_demo.py
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

try:
    from kg_query_demo import KnowledgeGraphQuery
except Exception as error:  # pragma: no cover - exercised only on import failure.
    KnowledgeGraphQuery = None  # type: ignore[assignment]
    IMPORT_ERROR: Optional[Exception] = error
else:
    IMPORT_ERROR = None


class EvidenceContextBuilder:
    """整理图谱查询结果，生成 LLM 可直接引用的结构化证据上下文。"""

    RELATION_TO_SECTION = {
        "has_manifestation": "主要皮损表现",
        "commonly_occurs_at": "常见部位",
        "has_symptom": "伴随症状",
        "recommended_examination": "建议检查",
        "differential_diagnosis": "鉴别诊断",
        "has_risk_warning": "风险提示",
        "has_medical_advice": "就医建议",
    }

    SECTION_ORDER = [
        "候选疾病",
        "主要皮损表现",
        "常见部位",
        "伴随症状",
        "建议检查",
        "鉴别诊断",
        "风险提示",
        "就医建议",
        "证据来源",
    ]

    def __init__(self, kg_query: Optional["KnowledgeGraphQuery"] = None) -> None:
        if KnowledgeGraphQuery is None:
            raise ImportError(
                "无法导入 KnowledgeGraphQuery。请确认 kg/kg_query_demo.py 存在、"
                "语法正确，并从项目根目录运行：python kg/kg_evidence_context_demo.py"
            ) from IMPORT_ERROR

        self.kg_query = kg_query or KnowledgeGraphQuery()

    @staticmethod
    def _evidence_path(triple: Dict[str, str]) -> str:
        """用 head_cn — relation_cn — tail_cn 表示一条证据路径。"""
        return (
            f"{triple.get('head_cn', '')} — "
            f"{triple.get('relation_cn', '')} — "
            f"{triple.get('tail_cn', '')}"
        )

    @staticmethod
    def _source_text(triple: Dict[str, str]) -> str:
        """保留 source 字段，并补充可用的 source_id/source_type。"""
        source = triple.get("source", "").strip()
        source_id = triple.get("source_id", "").strip()
        source_type = triple.get("source_type", "").strip()

        extras = ", ".join(item for item in (source_id, source_type) if item)
        if source and extras:
            return f"{source} ({extras})"
        return source or extras or "未标注"

    def _format_evidence_item(self, triple: Dict[str, str]) -> str:
        """格式化单条证据，保留路径、原始证据文本和来源。"""
        return "\n".join(
            [
                f"- 证据路径：{self._evidence_path(triple)}",
                f"  evidence_text：{triple.get('evidence_text', '') or '未标注'}",
                f"  source：{self._source_text(triple)}",
            ]
        )

    @staticmethod
    def _format_section(title: str, lines: Iterable[str]) -> str:
        content = list(lines)
        if not content:
            content = ["- 暂无相关证据。"]
        return f"## {title}\n" + "\n".join(content)

    def _candidate_disease_lines(self, triples: List[Dict[str, str]]) -> List[str]:
        """根据查询命中的疾病 ID，补全中英文名称。"""
        lines: List[str] = []
        seen = set()

        for triple in triples:
            disease_id = triple.get("head_id", "")
            if disease_id in seen:
                continue
            seen.add(disease_id)

            entity = self.kg_query.entities_by_id.get(disease_id, {})
            name_cn = entity.get("name_cn") or triple.get("head_cn", "")
            name_en = entity.get("name_en", "")
            if name_en:
                lines.append(f"- {name_cn} / {name_en}（{disease_id}）")
            else:
                lines.append(f"- {name_cn}（{disease_id}）")

        return lines

    def _group_evidence(self, triples: List[Dict[str, str]]) -> Dict[str, List[str]]:
        """按 relation_en 将证据归入固定模块。"""
        grouped: Dict[str, List[str]] = defaultdict(list)
        for triple in triples:
            section = self.RELATION_TO_SECTION.get(triple.get("relation_en", ""))
            if section:
                grouped[section].append(self._format_evidence_item(triple))
        return grouped

    def _source_lines(self, triples: List[Dict[str, str]]) -> List[str]:
        """汇总去重后的证据来源，便于 LLM 追溯。"""
        lines: List[str] = []
        seen = set()

        for triple in triples:
            source = self._source_text(triple)
            if source in seen:
                continue
            seen.add(source)
            lines.append(f"- {source}")

        return lines

    def build_context_by_disease(self, disease_name: str) -> str:
        """输入疾病中文名、英文名或 disease_id，输出结构化证据文本。"""
        triples = self.kg_query.query_by_disease(disease_name)

        sections: Dict[str, List[str]] = {
            "候选疾病": self._candidate_disease_lines(triples),
            "证据来源": self._source_lines(triples),
        }
        sections.update(self._group_evidence(triples))

        if not triples:
            sections["候选疾病"] = [f"- 未查询到匹配疾病：{disease_name}"]

        return "\n\n".join(
            self._format_section(section, sections.get(section, []))
            for section in self.SECTION_ORDER
        )


def build_context_by_disease(disease_name: str) -> str:
    """便捷函数：按疾病名称或 disease_id 直接构建证据上下文。"""
    return EvidenceContextBuilder().build_context_by_disease(disease_name)


def print_context(title: str, content: str) -> None:
    print("=" * 80)
    print(title)
    print("=" * 80)
    print(content)
    print()


def main() -> None:
    try:
        builder = EvidenceContextBuilder()
    except ImportError as error:
        print(f"导入 KnowledgeGraphQuery 失败：{error}")
        return
    except FileNotFoundError as error:
        print(error)
        return

    print_context(
        '示例 1: build_context_by_disease("黑色素瘤")',
        builder.build_context_by_disease("黑色素瘤"),
    )
    print_context(
        '示例 2: build_context_by_disease("基底细胞癌")',
        builder.build_context_by_disease("基底细胞癌"),
    )


if __name__ == "__main__":
    main()
