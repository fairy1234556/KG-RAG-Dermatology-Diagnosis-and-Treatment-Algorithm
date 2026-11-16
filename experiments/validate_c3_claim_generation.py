"""C3 离线验收：python experiments/validate_c3_claim_generation.py。

真实 C1/C2 + 模拟模型；只检验提示词传递和格式保存，不证明模型遵循证据约束。
"""

from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pad_case_input import build_pad_input
from experiments.validate_c1_pipeline_integration import MockLLMClient, RecordingRanker
from rag.baseline_common import (
    BASELINE_SYSTEM_PROMPT, OUTPUT_JSON_INSTRUCTION, BaselineOutputError,
    build_structured_result, build_user_prompt, result_to_dict,
)
from rag.kg_rag_pipeline import KGRAGPipeline
from rag.schemas import KGRAGResult


class ClaimClient(MockLLMClient):
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def generate(self, user_prompt, system_prompt=None, json_mode=False):
        self.calls += 1
        self.system_prompt = system_prompt
        result = super().generate(user_prompt, system_prompt, json_mode)
        return replace(result, content=json.dumps(self.payload, ensure_ascii=False))


class C3ClaimGenerationTests(unittest.TestCase):
    def setUp(self):
        guard = patch("rag.kg_rag_pipeline.QwenLLMClient", side_effect=AssertionError("禁止真实 API"))
        guard.start()
        self.addCleanup(guard.stop)
        self.claim = {
            "claim_id": "CLAIM_001",
            "claim_text": "患者报告出血，与候选疾病的相关知识相符，但不能据此确诊。",
            "patient_fact_ids": ["PAD_BCC_001:bleed"],
            "kg_path_ids": ["PATH_TRI_031"],
        }
        self.payload = {
            "observation_match": ["患者报告出血。"],
            "supporting_evidence": ["图谱记录候选疾病可伴出血。"],
            "differential_diagnosis": [],
            "risk_warning": ["不能据此确诊。"],
            "medical_advice": ["建议皮肤科评估。"],
            "evidence_gap": ["缺少检查结果。"],
            "sources": [],
            "claims": [self.claim],
        }
        self.client = ClaimClient(self.payload)
        self.ranker = RecordingRanker()
        self.pipeline = KGRAGPipeline(ranker=self.ranker, client=self.client)

    def run_pad(self, removed=()):
        return self.pipeline.run(
            "PAD_BCC_001_C3", "基底细胞癌", top_k=100,
            **build_pad_input("PAD_BCC_001", removed),
        )

    def prompt_ledger(self):
        text = self.client.prompt.split("【C2 结构化证据台账】\n", 1)[1]
        return json.JSONDecoder().raw_decode(text)[0]

    def test_four_fields_saved_without_rewriting(self):
        result = self.run_pad()
        self.assertEqual(result_to_dict(result)["claims"], [self.claim])
        self.assertEqual(set(result_to_dict(result)["claims"][0]),
                         {"claim_id", "claim_text", "patient_fact_ids", "kg_path_ids"})
        self.assertEqual(self.client.calls, 1)
        self.assertTrue(self.client.json_mode)

    def test_actual_c2_snapshot_and_ids_reach_prompt(self):
        result = self.run_pad()
        ledger = self.prompt_ledger()
        self.assertEqual(ledger, result_to_dict(result)["evidence_ledger"])
        fact = next(f for f in ledger["patient_facts"] if f["fact_id"] == "PAD_BCC_001:bleed")
        path = next(p for p in ledger["paths"] if p["path_id"] == "PATH_TRI_031")
        self.assertEqual(fact["fact_state"], "present")
        self.assertTrue(fact["mapping_reliable"])
        self.assertIn(fact["fact_id"], path["matched_fact_ids"])
        self.assertEqual(path["triple_ids"], ["TRI_031"])
        self.assertEqual(path["claim_usage"], "PATIENT_SUPPORT")
        self.assertEqual({p["claim_usage"] for p in ledger["paths"]},
                         {"PATIENT_SUPPORT", "BACKGROUND_ONLY", "DIFFERENTIAL_ONLY"})

    def test_prompt_has_generation_constraints(self):
        self.run_pad()
        for instruction in (
            "不得编造患者症状、检查结果或病史", "只能引用输入 C2 结构化证据台账",
            "BACKGROUND_ONLY 只能描述 KG 背景知识", "不能描述成患者已经出现的表现",
            "DIFFERENTIAL_ONLY 只能用于鉴别说明", "不得强行支持候选疾病",
            "不能把候选疾病解释成已经确诊", "不得虚构路径编号", "missing 不等于 absent",
        ):
            self.assertIn(instruction, self.client.prompt)
        self.assertEqual(self.client.system_prompt, BASELINE_SYSTEM_PROMPT)

    def test_json_roundtrip_keeps_claims_and_ledger(self):
        result = self.run_pad()
        payload = result_to_dict(result)
        restored = KGRAGResult(**json.loads(json.dumps(payload, ensure_ascii=False)))
        self.assertEqual(result_to_dict(restored), payload)

    def test_no_paths_keeps_facts_and_empty_path_references(self):
        self.client.payload = {"claims": [{
            **self.claim,
            "claim_text": "患者报告出血，但没有可用 KG 路径，无法据此支持候选疾病。",
            "kg_path_ids": [],
        }]}
        with patch.object(self.ranker, "rank", return_value=([], [], 0)):
            result = self.run_pad()
        ledger = self.prompt_ledger()
        self.assertTrue(ledger["patient_facts"])
        self.assertEqual(ledger["paths"], [])
        self.assertIn("PAD_BCC_001:bleed", {f["fact_id"] for f in ledger["patient_facts"]})
        self.assertEqual(result.claims[0].kg_path_ids, [])
        self.assertEqual(result.evidence_paths, [])
        self.assertNotIn("PATH_TRI_031", self.client.prompt)
        self.assertIn("kg_path_ids 必须为 []", self.client.prompt)

    def test_deleted_fact_snapshot_has_no_stale_support(self):
        self.run_pad()
        self.client.payload = {"claims": []}
        result = self.run_pad(["bleed"])
        ledger = self.prompt_ledger()
        fact = next(f for f in ledger["patient_facts"] if f["fact_id"] == "PAD_BCC_001:bleed")
        self.assertEqual(fact["fact_state"], "missing")
        self.assertTrue(all(fact["fact_id"] not in p["matched_fact_ids"] for p in ledger["paths"]))
        self.assertEqual(result.claims, [])

    def test_existing_output_fields_and_old_payload_remain_compatible(self):
        result = self.run_pad()
        for field in ("observation_match", "supporting_evidence", "differential_diagnosis",
                      "risk_warning", "medical_advice", "evidence_gap"):
            self.assertEqual(getattr(result, field), self.payload[field])
        self.assertTrue(result.evidence_paths)
        self.assertTrue(result.sources)
        self.assertEqual(result.method, "kg_rag")
        self.assertEqual(result.run_status, "success")
        old_payload = result_to_dict(result)
        old_payload.pop("claims")
        self.assertEqual(KGRAGResult(**old_payload).claims, [])
        self.client.payload = {"supporting_evidence": ["旧响应"]}
        self.assertEqual(self.run_pad().claims, [])

    def test_shared_helpers_default_to_legacy_behavior(self):
        prompt = build_user_prompt("基底细胞癌", "患者出血", "旧方法")
        self.assertTrue(prompt.endswith(OUTPUT_JSON_INSTRUCTION))
        self.assertNotIn('"claims"', prompt)
        response = self.client.generate("mock")
        for method in ("llm", "rag", "kg_rag"):
            result = build_structured_result("OLD", method, "基底细胞癌", "患者出血", response)
            self.assertEqual(result.claims, [])
            self.assertEqual(result.supporting_evidence, self.payload["supporting_evidence"])

    def test_malformed_claims_raise_format_error(self):
        missing_field = dict(self.claim)
        missing_field.pop("patient_fact_ids")
        invalid_values = [
            None, "not-an-array", ["not-an-object"], [missing_field],
            [{**self.claim, "extra": "不允许额外字段"}],
            [{**self.claim, "claim_id": 123}], [{**self.claim, "claim_text": ""}],
            [{**self.claim, "patient_fact_ids": "PAD_BCC_001:bleed"}],
            [{**self.claim, "kg_path_ids": [123]}],
        ]
        for claims in invalid_values:
            with self.subTest(claims=claims):
                self.client.payload = {"claims": claims}
                response = self.client.generate("mock")
                with self.assertRaises(BaselineOutputError):
                    build_structured_result("BAD", "kg_rag", "基底细胞癌", "患者出血",
                                            response, include_claims=True)

    def test_c3_does_not_verify_or_correct_model_references(self):
        # 明确 C3 边界：格式合法的错误引用仍保留，后续由 C4 核验。
        self.client.payload = {"claims": [{**self.claim, "kg_path_ids": ["UNKNOWN_PATH"]}]}
        result = self.run_pad()
        self.assertEqual(result.claims[0].kg_path_ids, ["UNKNOWN_PATH"])
        self.assertEqual(self.client.calls, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
