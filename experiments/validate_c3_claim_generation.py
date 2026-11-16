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

    def test_prompt_distinguishes_all_three_fact_states(self):
        # 只检查真实台账和传入模型的约束，不以模拟回答证明模型会遵守约束。
        self.client.payload = {"claims": []}
        for fields, state in (({"itch": True}, "present"),
                              ({"itch": False}, "absent"), ({}, "missing")):
            with self.subTest(state=state):
                self.pipeline.run("STATE", "基底细胞癌", "", structured_fields=fields)
                fact = next(f for f in self.prompt_ledger()["patient_facts"]
                            if f["fact_id"] == "STATE:itch")
                self.assertEqual(fact["fact_state"], state)
                for instruction in (
                    "present：患者明确存在该表现",
                    "absent：患者明确不存在该表现",
                    "不能写成“未提及”“未知”",
                    "missing：患者没有提供该信息",
                    "不能写成“没有”“未见”",
                    "absent、missing 只能分别用于说明否认或信息缺口，不能作为阳性支持",
                ):
                    self.assertIn(instruction, self.client.prompt)

    def test_absent_fact_reaches_prompt_with_mandatory_reference_rule(self):
        self.client.payload = {"claims": []}
        self.pipeline.run("TEXT", "基底细胞癌", "患者面部出现结节，伴出血，未见瘙痒。")
        ledger = self.prompt_ledger()
        itch = next(f for f in ledger["patient_facts"] if f["entity_id"] == "SYM_002")
        self.assertEqual(itch["fact_state"], "absent")
        self.assertTrue(itch["fact_id"])
        self.assertTrue(all(itch["fact_id"] not in p["matched_fact_ids"] for p in ledger["paths"]))
        for instruction in (
            "claims 中每个涉及患者具体表现的陈述，都必须对应 C2 patient_facts 中已登记的事实",
            "patient_fact_ids 中列出所涉及的全部 fact_id",
            "否认或信息缺口的陈述也不例外",
            "引用 absent 事实时同样必须填写对应的 patient_fact_ids",
        ):
            self.assertIn(instruction, self.client.prompt)

    def test_unregistered_observation_is_not_a_license_to_invent_fact_ids(self):
        self.client.payload = {"claims": []}
        observation = "患者面部出现结节，伴出血，未见瘙痒。"
        result = self.pipeline.run("TEXT", "基底细胞癌", observation)
        self.assertEqual(result.user_observation, observation)
        self.assertEqual({f["entity_id"] for f in self.prompt_ledger()["patient_facts"]},
                         {"SITE_005", "SYM_001", "SYM_002"})
        for instruction in (
            "即使原始观察包含某个表现，只要 C2 未登记对应患者事实",
            "就不要将该表现写入 claims 的患者陈述",
            "不得为未登记的事实自行编造 fact_id",
            "不得借用其他事实的编号代替",
            "BACKGROUND_ONLY 和 DIFFERENTIAL_ONLY 均不能作为候选疾病的患者级直接支持",
        ):
            self.assertIn(instruction, self.client.prompt)

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

    def test_truncated_response_is_reported_before_json_parsing(self):
        response = self.client.generate("mock")
        # 即使被截断的内容碰巧是合法 JSON，也不能将其当作完整的 C3 输出。
        for content in ('{"claims": [{"claim_id": "CLAIM_001"}', '{"claims": []}'):
            with self.subTest(content=content):
                truncated = replace(response, content=content, finish_reason="length",
                                    completion_tokens=800, max_completion_tokens=800)
                with self.assertRaises(BaselineOutputError) as caught:
                    build_structured_result("LIMIT", "kg_rag", "基底细胞癌", "患者出血",
                                            truncated, include_claims=True)
                message = str(caught.exception)
                self.assertIn("因长度限制被截断", message)
                self.assertIn("finish_reason='length'", message)
                self.assertIn("completion_tokens=800", message)
                self.assertIn("max_completion_tokens=800", message)
                self.assertIn("configs/llm_config.yaml", message)

    def test_invalid_complete_json_reports_metadata_without_repair_or_raw_content(self):
        response = replace(self.client.generate("mock"),
                           content='{"claims": [] "private_patient_text": "do not log"}',
                           finish_reason="stop", completion_tokens=120,
                           max_completion_tokens=2400)
        with self.assertRaises(BaselineOutputError) as caught:
            build_structured_result("INVALID", "kg_rag", "基底细胞癌", "患者出血",
                                    response, include_claims=True)
        message = str(caught.exception)
        self.assertIn("JSON 格式无效", message)
        self.assertIn("finish_reason='stop'", message)
        self.assertIn("completion_tokens=120", message)
        self.assertIn("max_completion_tokens=2400", message)
        self.assertNotIn("被截断", message)
        self.assertNotIn("private_patient_text", message)
        # 旧方法的默认错误信息不受 C3 诊断信息影响。
        with self.assertRaises(BaselineOutputError) as legacy:
            build_structured_result("OLD", "llm", "基底细胞癌", "患者出血", response)
        self.assertNotIn("finish_reason", str(legacy.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
