"""
Validate the ordinary RAG text retriever.

This validation does not call the real LLM API.

Run:

    python experiments/validate_text_retriever.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import List, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from rag.text_retriever import BM25TextRetriever
from rag.text_retriever import RetrievedDocument
from rag.text_retriever import load_corpus


CORPUS_FILE = (
    PROJECT_ROOT
    / "rag"
    / "data"
    / "evidence_corpus_v1.jsonl"
)

RETRIEVER_FILE = (
    PROJECT_ROOT
    / "rag"
    / "text_retriever.py"
)


def print_separator() -> None:
    print("=" * 70)


def check_score_order(
    results: List[RetrievedDocument],
) -> bool:
    """检查检索结果是否按总分降序排列。"""

    scores = [
        result.score
        for result in results
    ]

    return scores == sorted(
        scores,
        reverse=True,
    )


def check_rank_order(
    results: List[RetrievedDocument],
) -> bool:
    """检查 rank 是否从 1 开始连续递增。"""

    actual_ranks = [
        result.rank
        for result in results
    ]

    expected_ranks = list(
        range(
            1,
            len(results) + 1,
        )
    )

    return actual_ranks == expected_ranks


def result_signature(
    results: List[RetrievedDocument],
) -> List[Tuple[str, float]]:
    """生成用于确定性检查的结果签名。"""

    return [
        (
            result.document_id,
            result.score,
        )
        for result in results
    ]


def validate_corpus() -> bool:
    """验证扁平文本语料库的基本结构。"""

    errors: List[str] = []

    try:
        documents = load_corpus(
            CORPUS_FILE
        )

    except Exception as exc:
        documents = []
        errors.append(
            f"语料库加载失败：{exc}"
        )

    if not documents:
        errors.append(
            "语料库中没有有效文档。"
        )

    document_ids = [
        document.document_id
        for document in documents
    ]

    if len(document_ids) != len(
        set(document_ids)
    ):
        errors.append(
            "语料库存在重复 document_id。"
        )

    empty_documents = [
        document.document_id
        for document in documents
        if not document.text.strip()
    ]

    if empty_documents:
        errors.append(
            "存在空文本证据文档："
            f"{empty_documents}"
        )

    print_separator()
    print(
        "TEXT_RETRIEVER_001："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：扁平文本语料库结构检查")
    print(f"文档数量：{len(documents)}")
    print(
        "重复 document_id："
        f"{len(document_ids) - len(set(document_ids))}"
    )
    print(
        f"空文本数量：{len(empty_documents)}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_typical_retrieval() -> bool:
    """验证基底细胞癌典型文本的 Top-k 检索。"""

    errors: List[str] = []

    retriever = BM25TextRetriever(
        corpus_file=CORPUS_FILE
    )

    results = retriever.retrieve(
        candidate_disease="基底细胞癌",
        user_observation=(
            "患者面部出现光亮的珍珠样结节，"
            "表面可见细小血管。"
        ),
        top_k=5,
    )

    if len(results) != 5:
        errors.append(
            "Top-k 返回数量不为 5，"
            f"实际为 {len(results)}。"
        )

    if not check_rank_order(results):
        errors.append(
            "检索结果 rank 不连续。"
        )

    if not check_score_order(results):
        errors.append(
            "检索结果没有按 score 降序排列。"
        )

    if any(
        result.score <= 0
        for result in results
    ):
        errors.append(
            "Top-k 中存在得分不大于 0 的文档。"
        )

    combined_text = "\n".join(
        result.text
        for result in results
    )

    expected_phrase_groups = [
        (
            "珍珠样结节",
            "珍珠样",
        ),
        (
            "毛细血管",
            "细小血管",
            "血管扩张",
        ),
        (
            "面部",
            "头面部",
        ),
    ]

    matched_groups = []

    for phrase_group in expected_phrase_groups:
        if any(
            phrase in combined_text
            for phrase in phrase_group
        ):
            matched_groups.append(
                phrase_group
            )

    # 普通 RAG 不进行实体映射，因此不要求三个概念全部召回。
    # 召回至少两个典型概念即可通过初步检查。
    if len(matched_groups) < 2:
        errors.append(
            "典型证据召回不足："
            f"仅匹配 {len(matched_groups)} 组。"
        )

    if not any(
        result.source_names
        for result in results
    ):
        errors.append(
            "Top-k 结果全部缺少来源信息。"
        )

    print_separator()
    print(
        "TEXT_RETRIEVER_002："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：基底细胞癌典型证据召回")
    print(f"返回数量：{len(results)}")
    print(
        f"典型概念匹配组数：{len(matched_groups)}/3"
    )

    for result in results:
        print(
            f"- Rank {result.rank}: "
            f"{result.document_id} | "
            f"score={result.score:.6f} | "
            f"text={result.text}"
        )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_deterministic_retrieval() -> bool:
    """验证相同查询重复运行时结果一致。"""

    errors: List[str] = []

    retriever = BM25TextRetriever(
        corpus_file=CORPUS_FILE
    )

    query_parameters = {
        "candidate_disease": "黑色素瘤",
        "user_observation": (
            "皮损形态不对称，边界不规则，"
            "并可见多种颜色。"
        ),
        "top_k": 5,
    }

    first_results = retriever.retrieve(
        **query_parameters
    )

    second_results = retriever.retrieve(
        **query_parameters
    )

    first_signature = result_signature(
        first_results
    )

    second_signature = result_signature(
        second_results
    )

    if first_signature != second_signature:
        errors.append(
            "相同查询的两次检索结果不一致。"
        )

    print_separator()
    print(
        "TEXT_RETRIEVER_003："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：检索确定性检查")
    print(
        f"第一次结果：{first_signature}"
    )
    print(
        f"第二次结果：{second_signature}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_input_constraints() -> bool:
    """验证检索输入参数约束。"""

    errors: List[str] = []

    retriever = BM25TextRetriever(
        corpus_file=CORPUS_FILE
    )

    invalid_cases = [
        {
            "candidate_disease": "",
            "user_observation": "面部出现结节。",
            "top_k": 5,
            "name": "空候选疾病",
        },
        {
            "candidate_disease": "基底细胞癌",
            "user_observation": "",
            "top_k": 5,
            "name": "空观察文本",
        },
        {
            "candidate_disease": "基底细胞癌",
            "user_observation": "面部出现结节。",
            "top_k": 0,
            "name": "非法 top_k",
        },
    ]

    for case in invalid_cases:
        try:
            retriever.retrieve(
                candidate_disease=case[
                    "candidate_disease"
                ],
                user_observation=case[
                    "user_observation"
                ],
                top_k=case["top_k"],
            )

            errors.append(
                f"{case['name']} 未触发 ValueError。"
            )

        except ValueError:
            pass

    print_separator()
    print(
        "TEXT_RETRIEVER_004："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：输入参数约束检查")

    for error in errors:
        print(f"错误：{error}")

    return not errors


def validate_graph_isolation() -> bool:
    """验证普通 RAG 检索器没有导入知识图谱模块。"""

    errors: List[str] = []

    source_code = RETRIEVER_FILE.read_text(
        encoding="utf-8-sig"
    )

    forbidden_import_patterns = [
        r"^\s*from\s+kg\.",
        r"^\s*import\s+kg(?:\.|\s|$)",
        r"^\s*from\s+rag\.semantic_anchor",
        r"^\s*import\s+rag\.semantic_anchor",
    ]

    matched_patterns = []

    for pattern in forbidden_import_patterns:
        if re.search(
            pattern,
            source_code,
            flags=re.MULTILINE,
        ):
            matched_patterns.append(pattern)

    if matched_patterns:
        errors.append(
            "普通 RAG 检索器导入了知识图谱相关模块："
            f"{matched_patterns}"
        )

    print_separator()
    print(
        "TEXT_RETRIEVER_005："
        f"{'通过' if not errors else '失败'}"
    )
    print("测试名称：普通 RAG 与知识图谱模块隔离检查")
    print(
        "发现图谱模块导入："
        f"{matched_patterns}"
    )

    for error in errors:
        print(f"错误：{error}")

    return not errors


def main() -> int:
    validation_results = [
        validate_corpus(),
        validate_typical_retrieval(),
        validate_deterministic_retrieval(),
        validate_input_constraints(),
        validate_graph_isolation(),
    ]

    print_separator()

    passed_count = sum(
        1
        for passed in validation_results
        if passed
    )

    total_count = len(
        validation_results
    )

    if passed_count == total_count:
        print(
            "普通 RAG 文本检索验证通过："
            f"{total_count} 组检查全部通过。"
        )
        return 0

    print(
        "普通 RAG 文本检索验证未通过："
        f"{total_count - passed_count} 组检查失败。"
    )
    print(
        f"通过数量：{passed_count}/{total_count}"
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(main())