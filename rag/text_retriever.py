"""
BM25 text retriever for the ordinary RAG baseline.

This module retrieves evidence from a flat JSONL text corpus.

It does not use:

- knowledge graph edges;
- entity relations;
- graph traversal;
- semantic anchor mapping;
- KG path ranking.

Examples:

    python rag/text_retriever.py \
        --disease "基底细胞癌" \
        --observation "患者面部出现珍珠样结节，表面可见细小血管。" \
        --top-k 5
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


DEFAULT_CORPUS_FILE = (
    PROJECT_ROOT
    / "rag"
    / "data"
    / "evidence_corpus_v1.jsonl"
)


@dataclass(frozen=True)
class TextDocument:
    """普通 RAG 语料库中的扁平文本记录。"""

    document_id: str
    text: str
    source_names: Tuple[str, ...]
    origin_record_ids: Tuple[str, ...]


@dataclass(frozen=True)
class RetrievedDocument:
    """普通 RAG 的单条文本检索结果。"""

    rank: int
    document_id: str
    text: str
    score: float
    bm25_score: float
    phrase_overlap_score: float
    matched_terms: Tuple[str, ...]
    source_names: Tuple[str, ...]
    origin_record_ids: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        result = asdict(self)

        result["matched_terms"] = list(
            self.matched_terms
        )
        result["source_names"] = list(
            self.source_names
        )
        result["origin_record_ids"] = list(
            self.origin_record_ids
        )

        return result


def normalize_text(text: str) -> str:
    """统一大小写、空白和常见标点。"""

    normalized = (
        text or ""
    ).strip().lower()

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized


def tokenize(text: str) -> List[str]:
    """
    对中英文医学文本进行轻量分词。

    中文部分使用：

    - 单字；
    - 相邻双字。

    英文和数字部分使用连续词元。

    该方法不依赖 jieba 或向量模型，便于实验复现。
    """

    normalized = normalize_text(text)

    tokens: List[str] = []

    chinese_segments = re.findall(
        r"[\u4e00-\u9fff]+",
        normalized,
    )

    for segment in chinese_segments:
        characters = list(segment)

        tokens.extend(characters)

        tokens.extend(
            segment[index : index + 2]
            for index in range(
                len(segment) - 1
            )
        )

    latin_tokens = re.findall(
        r"[a-z0-9]+(?:[-_][a-z0-9]+)*",
        normalized,
    )

    tokens.extend(latin_tokens)

    return [
        token
        for token in tokens
        if token
    ]


def unique_preserve_order(
    values: Sequence[str],
) -> Tuple[str, ...]:
    """保留原始顺序并去重。"""

    result: List[str] = []
    seen = set()

    for value in values:
        cleaned = (
            value or ""
        ).strip()

        if not cleaned:
            continue

        if cleaned in seen:
            continue

        seen.add(cleaned)
        result.append(cleaned)

    return tuple(result)


def load_corpus(
    corpus_file: Path = DEFAULT_CORPUS_FILE,
) -> List[TextDocument]:
    """读取普通 RAG JSONL 语料库。"""

    if not corpus_file.exists():
        raise FileNotFoundError(
            f"找不到普通 RAG 语料库：{corpus_file}"
        )

    documents: List[TextDocument] = []

    with corpus_file.open(
        "r",
        encoding="utf-8-sig",
    ) as file:
        for line_number, raw_line in enumerate(
            file,
            start=1,
        ):
            line = raw_line.strip()

            if not line:
                continue

            try:
                payload = json.loads(line)

            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"语料库第 {line_number} 行不是有效 JSON："
                    f"{exc}"
                ) from exc

            if not isinstance(payload, dict):
                raise ValueError(
                    f"语料库第 {line_number} 行必须是 JSON 对象。"
                )

            document_id = str(
                payload.get(
                    "document_id",
                    "",
                )
            ).strip()

            text = str(
                payload.get(
                    "text",
                    "",
                )
            ).strip()

            if not document_id:
                raise ValueError(
                    f"语料库第 {line_number} 行缺少 document_id。"
                )

            if not text:
                raise ValueError(
                    f"语料库第 {line_number} 行缺少 text。"
                )

            source_names_value = payload.get(
                "source_names",
                [],
            )

            origin_ids_value = payload.get(
                "origin_record_ids",
                [],
            )

            if not isinstance(
                source_names_value,
                list,
            ):
                raise ValueError(
                    f"语料库第 {line_number} 行的 "
                    "source_names 必须是数组。"
                )

            if not isinstance(
                origin_ids_value,
                list,
            ):
                raise ValueError(
                    f"语料库第 {line_number} 行的 "
                    "origin_record_ids 必须是数组。"
                )

            documents.append(
                TextDocument(
                    document_id=document_id,
                    text=text,
                    source_names=(
                        unique_preserve_order(
                            [
                                str(value)
                                for value
                                in source_names_value
                            ]
                        )
                    ),
                    origin_record_ids=(
                        unique_preserve_order(
                            [
                                str(value)
                                for value
                                in origin_ids_value
                            ]
                        )
                    ),
                )
            )

    if not documents:
        raise ValueError(
            "普通 RAG 语料库中没有有效文档。"
        )

    document_ids = [
        document.document_id
        for document in documents
    ]

    if len(document_ids) != len(
        set(document_ids)
    ):
        raise ValueError(
            "普通 RAG 语料库存在重复 document_id。"
        )

    return documents


class BM25TextRetriever:
    """基于 BM25 的普通文本检索器。"""

    def __init__(
        self,
        corpus_file: Path = DEFAULT_CORPUS_FILE,
        k1: float = 1.5,
        b: float = 0.75,
        phrase_overlap_weight: float = 0.35,
    ) -> None:
        if k1 <= 0:
            raise ValueError(
                "BM25 参数 k1 必须大于 0。"
            )

        if not 0 <= b <= 1:
            raise ValueError(
                "BM25 参数 b 必须位于 0 到 1 之间。"
            )

        if phrase_overlap_weight < 0:
            raise ValueError(
                "phrase_overlap_weight 不能小于 0。"
            )

        self.corpus_file = Path(
            corpus_file
        )

        self.k1 = float(k1)
        self.b = float(b)
        self.phrase_overlap_weight = float(
            phrase_overlap_weight
        )

        self.documents = load_corpus(
            self.corpus_file
        )

        self.document_tokens: List[
            List[str]
        ] = [
            tokenize(document.text)
            for document in self.documents
        ]

        self.document_term_frequencies: List[
            Dict[str, int]
        ] = [
            self._count_terms(tokens)
            for tokens in self.document_tokens
        ]

        self.document_lengths = [
            len(tokens)
            for tokens in self.document_tokens
        ]

        self.average_document_length = (
            sum(self.document_lengths)
            / len(self.document_lengths)
        )

        self.document_frequencies = (
            self._build_document_frequencies()
        )

    @staticmethod
    def _count_terms(
        tokens: Sequence[str],
    ) -> Dict[str, int]:
        """统计单篇文档中的词频。"""

        frequencies: Dict[
            str,
            int,
        ] = {}

        for token in tokens:
            frequencies[token] = (
                frequencies.get(
                    token,
                    0,
                )
                + 1
            )

        return frequencies

    def _build_document_frequencies(
        self,
    ) -> Dict[str, int]:
        """统计每个词元出现于多少篇文档。"""

        frequencies: Dict[
            str,
            int,
        ] = {}

        for tokens in self.document_tokens:
            for token in set(tokens):
                frequencies[token] = (
                    frequencies.get(
                        token,
                        0,
                    )
                    + 1
                )

        return frequencies

    def _inverse_document_frequency(
        self,
        term: str,
    ) -> float:
        """计算 BM25 的 IDF。"""

        document_count = len(
            self.documents
        )

        document_frequency = (
            self.document_frequencies.get(
                term,
                0,
            )
        )

        return math.log(
            1.0
            + (
                document_count
                - document_frequency
                + 0.5
            )
            / (
                document_frequency
                + 0.5
            )
        )

    def _calculate_bm25_score(
        self,
        query_terms: Sequence[str],
        document_index: int,
    ) -> float:
        """计算查询与单篇文档之间的 BM25 得分。"""

        term_frequencies = (
            self.document_term_frequencies[
                document_index
            ]
        )

        document_length = (
            self.document_lengths[
                document_index
            ]
        )

        score = 0.0

        for term in set(query_terms):
            term_frequency = (
                term_frequencies.get(
                    term,
                    0,
                )
            )

            if term_frequency <= 0:
                continue

            idf = (
                self._inverse_document_frequency(
                    term
                )
            )

            denominator = (
                term_frequency
                + self.k1
                * (
                    1.0
                    - self.b
                    + self.b
                    * document_length
                    / max(
                        self.average_document_length,
                        1.0,
                    )
                )
            )

            score += (
                idf
                * (
                    term_frequency
                    * (
                        self.k1
                        + 1.0
                    )
                )
                / denominator
            )

        return score

    @staticmethod
    def _extract_query_phrases(
        candidate_disease: str,
        user_observation: str,
    ) -> Tuple[str, ...]:
        """
        提取可用于精确重合加分的短语。

        普通 RAG 仅使用用户输入文本本身，
        不进行知识图谱实体映射。
        """

        phrases: List[str] = []

        disease = normalize_text(
            candidate_disease
        )

        if disease:
            phrases.append(disease)

        observation_parts = re.split(
            r"[，,。；;、：:\s]+",
            normalize_text(
                user_observation
            ),
        )

        for part in observation_parts:
            cleaned = part.strip()

            if len(cleaned) >= 2:
                phrases.append(cleaned)

        return unique_preserve_order(
            phrases
        )

    def _calculate_phrase_overlap_score(
        self,
        candidate_disease: str,
        user_observation: str,
        document_text: str,
    ) -> Tuple[
        float,
        Tuple[str, ...],
    ]:
        """计算查询短语与证据文本的直接重合加分。"""

        normalized_document = (
            normalize_text(
                document_text
            )
        )

        phrases = (
            self._extract_query_phrases(
                candidate_disease,
                user_observation,
            )
        )

        matched_phrases = [
            phrase
            for phrase in phrases
            if phrase
            and phrase
            in normalized_document
        ]

        score = (
            len(matched_phrases)
            * self.phrase_overlap_weight
        )

        return (
            score,
            unique_preserve_order(
                matched_phrases
            ),
        )

    def retrieve(
        self,
        candidate_disease: str,
        user_observation: str,
        top_k: int = 5,
    ) -> List[RetrievedDocument]:
        """检索与候选疾病和用户观察最相关的文本片段。"""

        disease = (
            candidate_disease or ""
        ).strip()

        observation = (
            user_observation or ""
        ).strip()

        if not disease:
            raise ValueError(
                "candidate_disease 不能为空。"
            )

        if not observation:
            raise ValueError(
                "user_observation 不能为空。"
            )

        if top_k <= 0:
            raise ValueError(
                "top_k 必须大于 0。"
            )

        query_text = (
            disease
            + " "
            + observation
        )

        query_terms = tokenize(
            query_text
        )

        if not query_terms:
            raise ValueError(
                "查询文本无法生成有效检索词元。"
            )

        scored_items = []

        for index, document in enumerate(
            self.documents
        ):
            bm25_score = (
                self._calculate_bm25_score(
                    query_terms=query_terms,
                    document_index=index,
                )
            )

            (
                phrase_overlap_score,
                matched_phrases,
            ) = (
                self._calculate_phrase_overlap_score(
                    candidate_disease=disease,
                    user_observation=observation,
                    document_text=document.text,
                )
            )

            total_score = (
                bm25_score
                + phrase_overlap_score
            )

            if total_score <= 0:
                continue

            matched_terms = (
                unique_preserve_order(
                    [
                        term
                        for term in query_terms
                        if term
                        in self.document_term_frequencies[
                            index
                        ]
                    ]
                    + list(matched_phrases)
                )
            )

            scored_items.append(
                {
                    "document": document,
                    "bm25_score": bm25_score,
                    "phrase_overlap_score": (
                        phrase_overlap_score
                    ),
                    "total_score": total_score,
                    "matched_terms": (
                        matched_terms
                    ),
                }
            )

        scored_items.sort(
            key=lambda item: (
                -item["total_score"],
                -item["phrase_overlap_score"],
                -item["bm25_score"],
                item["document"].document_id,
            )
        )

        selected_items = scored_items[
            :top_k
        ]

        results: List[
            RetrievedDocument
        ] = []

        for rank, item in enumerate(
            selected_items,
            start=1,
        ):
            document = item["document"]

            results.append(
                RetrievedDocument(
                    rank=rank,
                    document_id=(
                        document.document_id
                    ),
                    text=document.text,
                    score=round(
                        item["total_score"],
                        6,
                    ),
                    bm25_score=round(
                        item["bm25_score"],
                        6,
                    ),
                    phrase_overlap_score=round(
                        item[
                            "phrase_overlap_score"
                        ],
                        6,
                    ),
                    matched_terms=(
                        item["matched_terms"]
                    ),
                    source_names=(
                        document.source_names
                    ),
                    origin_record_ids=(
                        document.origin_record_ids
                    ),
                )
            )

        return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "运行普通 RAG 的 BM25 文本检索。"
        )
    )

    parser.add_argument(
        "--disease",
        required=True,
        help="候选疾病名称",
    )

    parser.add_argument(
        "--observation",
        required=True,
        help="用户观察文本",
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="返回文本证据数量，默认 5",
    )

    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS_FILE,
        help="普通 RAG JSONL 语料库路径",
    )

    args = parser.parse_args()

    try:
        retriever = BM25TextRetriever(
            corpus_file=args.corpus
        )

        results = retriever.retrieve(
            candidate_disease=args.disease,
            user_observation=(
                args.observation
            ),
            top_k=args.top_k,
        )

    except (
        FileNotFoundError,
        ValueError,
        TypeError,
    ) as exc:
        print(
            f"普通 RAG 文本检索失败：{exc}"
        )
        return 1

    output = {
        "candidate_disease": (
            args.disease.strip()
        ),
        "user_observation": (
            args.observation.strip()
        ),
        "top_k": args.top_k,
        "retrieved_count": len(results),
        "retrieval_method": (
            "bm25_with_phrase_overlap"
        ),
        "documents": [
            result.to_dict()
            for result in results
        ],
    }

    print(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())