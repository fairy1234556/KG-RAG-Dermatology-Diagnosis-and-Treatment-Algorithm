"""运行：.venv/bin/python experiments/validate_c4_claim_verification.py。

真实 C1/C2 路径 + 预设模拟回答，只验证流程与提示词，不证明千问的语义判断准确率。
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

from experiments.validate_c1_pipeline_integration import MockLLMClient, RecordingRanker
from rag.baseline_common import result_to_dict
from rag.claim_verifier import reference_errors, review_claims
from rag.kg_rag_pipeline import KGRAGPipeline
from rag.llm_client import LLMClientError, LLMResult
from rag.schemas import EvidenceClaim, KGRAGResult


PASSED = {"status": "passed", "reasons": []}


class ScriptedClient(MockLLMClient):
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def generate(self, user_prompt, system_prompt=None, json_mode=False):
        self.calls.append({"user": user_prompt, "system": system_prompt, "json_mode": json_mode})
        if not self.replies:
            raise AssertionError("出现了未预期的模型调用或重复矫正")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, LLMResult):
            return reply
        base = super().generate(user_prompt, system_prompt, json_mode)
        return replace(base, content=reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False))


class C4ClaimVerificationTests(unittest.TestCase):
    def setUp(self):
        guard = patch("rag.kg_rag_pipeline.QwenLLMClient", side_effect=AssertionError("禁止真实 API"))
        guard.start()
        self.addCleanup(guard.stop)
        self.observation = "患者面部出现结节，伴出血，未见瘙痒。"
        self.ranker = RecordingRanker()
        self.base = KGRAGPipeline(ranker=self.ranker, client=MockLLMClient()).run(
            "TEXT", "基底细胞癌", self.observation, top_k=100,
        )
        self.paths = self.ranker.result[1]
        self.ledger = self.base.evidence_ledger

    def claim(self, **updates):
        fields = {
            "claim_id": "CLAIM_001", "claim_text": "患者报告出血，与相关知识相符，但不能据此确诊。",
            "patient_fact_ids": ["TEXT:text:SYM_001"], "kg_path_ids": ["PATH_TRI_031"],
        }
        fields.update(updates)
        return EvidenceClaim(**fields)

    def review(self, claim, replies, paths=None):
        self.client = ScriptedClient(replies)
        return review_claims(
            [claim], self.ledger, self.paths if paths is None else paths,
            "基底细胞癌", self.observation, self.client,
        )[0]

    @staticmethod
    def dump(model):
        return model.model_dump() if hasattr(model, "model_dump") else model.dict()

    def test_correct_claim_passes_without_changes(self):
        original = self.claim()
        record = self.review(original, [PASSED])
        self.assertEqual(record.final_status, "passed")
        self.assertEqual(record.original_claim, original)
        self.assertIsNone(record.corrected_claim)
        self.assertIsNone(record.recheck)
        self.assertEqual(len(self.client.calls), 1)

    def test_missing_fact_id_cannot_be_overruled_by_llm_pass(self):
        original = self.claim(patient_fact_ids=["UNKNOWN_FACT"])
        corrected = self.claim()
        record = self.review(original, [PASSED, self.dump(corrected), PASSED])
        self.assertEqual(record.verification.status, "failed")
        self.assertIn("患者事实编号不存在：UNKNOWN_FACT", record.verification.reasons)
        self.assertEqual(record.final_status, "corrected")
        self.assertEqual(record.corrected_claim.claim_id, original.claim_id)
        self.assertEqual(record.original_claim.patient_fact_ids, ["UNKNOWN_FACT"])

    def test_missing_path_id_is_detected(self):
        original = self.claim(kg_path_ids=["UNKNOWN_PATH"])
        record = self.review(original, [PASSED, self.dump(self.claim()), PASSED])
        self.assertIn("KG 路径编号不存在：UNKNOWN_PATH", record.verification.reasons)
        self.assertEqual(record.final_status, "corrected")

    def test_absent_fact_is_legal_when_described_as_denied(self):
        claim = self.claim(claim_text="患者明确否认瘙痒。",
                           patient_fact_ids=["TEXT:text:SYM_002"], kg_path_ids=[])
        self.assertEqual(reference_errors(claim, self.ledger), [])
        record = self.review(claim, [PASSED])
        self.assertEqual(record.final_status, "passed")
        self.assertIsNone(record.corrected_claim)

    def test_absent_misread_as_missing_is_corrected_once(self):
        original = self.claim(claim_text="患者未提及瘙痒。",
                              patient_fact_ids=["TEXT:text:SYM_002"], kg_path_ids=[])
        corrected = self.claim(claim_text="患者明确否认瘙痒。",
                               patient_fact_ids=["TEXT:text:SYM_002"], kg_path_ids=[])
        reason = "事实状态错误：瘙痒为 absent，不能说成未提及。"
        record = self.review(original, [{"status": "failed", "reasons": [reason]},
                                       self.dump(corrected), PASSED])
        self.assertEqual(record.verification.reasons, [reason])
        self.assertEqual(record.corrected_claim, corrected)
        self.assertEqual(record.recheck.status, "passed")
        self.assertEqual(record.final_status, "corrected")
        self.assertEqual(len(self.client.calls), 3)
        payload = json.loads(self.client.calls[1]["user"])
        self.assertEqual(payload["problems"], [reason])
        self.assertEqual(payload["claim"], self.dump(original))

    def test_simulated_state_and_role_errors_are_routed_to_correction(self):
        cases = [
            (self.claim(claim_text="患者有瘙痒。", patient_fact_ids=["TEXT:text:SYM_002"], kg_path_ids=[]),
             "absent 被说成存在"),
            (self.claim(claim_text="患者有珍珠样结节。", patient_fact_ids=[], kg_path_ids=["PATH_TRI_025"]),
             "KG 背景知识被描述为患者表现"),
            (self.claim(claim_text="黑色素瘤出血的知识直接支持患者患有基底细胞癌。",
                        kg_path_ids=["PATH_TRI_035_TRI_007"]), "鉴别证据被当作直接支持"),
            (self.claim(claim_text="出血足以确诊基底细胞癌。"), "证据无法支持的医学描述"),
        ]
        for original, reason in cases:
            with self.subTest(reason=reason):
                corrected = self.claim(claim_text="现有证据不足以确认候选疾病。",
                                       patient_fact_ids=[], kg_path_ids=[])
                record = self.review(original, [{"status": "failed", "reasons": [reason]},
                                               self.dump(corrected), PASSED])
                self.assertEqual(record.verification.reasons, [reason])
                self.assertEqual(record.final_status, "corrected")

    def test_missing_state_misread_as_present_or_absent(self):
        base = KGRAGPipeline(ranker=self.ranker, client=MockLLMClient()).run(
            "PAD", "基底细胞癌", "旧文本：患者瘙痒", structured_fields={"bleed": True}, top_k=100,
        )
        self.ledger, self.paths, self.observation = base.evidence_ledger, self.ranker.result[1], base.user_observation
        for text in ("患者有瘙痒。", "患者未见瘙痒。"):
            with self.subTest(text=text):
                original = self.claim(claim_text=text, patient_fact_ids=["PAD:itch"], kg_path_ids=[])
                corrected = self.claim(claim_text="患者未提供瘙痒信息。",
                                       patient_fact_ids=["PAD:itch"], kg_path_ids=[])
                record = self.review(original, [{"status": "failed", "reasons": ["missing 事实状态错误"]},
                                               self.dump(corrected), PASSED])
                self.assertEqual(record.final_status, "corrected")
                self.assertNotIn("旧文本", self.client.calls[0]["user"])

    def test_unregistered_nodule_is_incomplete_citation_not_absence(self):
        original = self.claim(claim_text="患者面部出现结节并伴出血。",
                              patient_fact_ids=["TEXT:text:SITE_005", "TEXT:text:SYM_001"])
        self.assertEqual(reference_errors(original, self.ledger), [])
        corrected = self.claim(claim_text="患者报告的部位为面部，并伴有出血，尚不能据此确诊。",
                               patient_fact_ids=original.patient_fact_ids)
        reason = "证据引用不完整：原始观察中的结节未登记为 C2 事实，不能认定患者没有结节。"
        record = self.review(original, [{"status": "failed", "reasons": [reason]},
                                       self.dump(corrected), PASSED])
        self.assertEqual(record.verification.reasons, [reason])
        self.assertEqual(record.final_status, "corrected")
        prompt = self.client.calls[0]
        self.assertIn("不能认定患者没有该表现", prompt["system"])
        self.assertIn("证据引用不完整", prompt["system"])
        self.assertEqual(json.loads(prompt["user"])["user_observation"], self.observation)

    def test_background_and_differential_references_are_not_automatically_errors(self):
        for path_id, text in (("PATH_TRI_025", "一般知识中候选疾病可表现为珍珠样结节。"),
                              ("PATH_TRI_035_TRI_007", "出血可见于其他疾病，需要考虑鉴别。")):
            with self.subTest(path_id=path_id):
                claim = self.claim(claim_text=text, patient_fact_ids=[], kg_path_ids=[path_id])
                self.assertEqual(reference_errors(claim, self.ledger), [])
                self.assertEqual(self.review(claim, [PASSED]).final_status, "passed")

    def test_still_failed_after_correction_is_unresolved_without_retry(self):
        failed = {"status": "failed", "reasons": ["仍然超出证据范围"]}
        record = self.review(self.claim(), [failed, self.dump(self.claim()), failed])
        self.assertEqual(record.final_status, "unresolved")
        self.assertEqual(record.recheck.status, "failed")
        self.assertEqual(len(self.client.calls), 3)

    def test_invalid_corrected_reference_is_checked_again(self):
        failed = {"status": "failed", "reasons": ["需要修改"]}
        corrected = self.claim(kg_path_ids=["NEW_FAKE_PATH"])
        record = self.review(self.claim(), [failed, self.dump(corrected), PASSED])
        self.assertEqual(record.final_status, "unresolved")
        self.assertIn("KG 路径编号不存在：NEW_FAKE_PATH", record.recheck.reasons)

    def test_changed_claim_id_is_rejected(self):
        failed = {"status": "failed", "reasons": ["需要修改"]}
        record = self.review(self.claim(), [failed, self.dump(self.claim(claim_id="CHANGED"))])
        self.assertEqual(record.claim_id, "CLAIM_001")
        self.assertIsNone(record.corrected_claim)
        self.assertEqual(record.final_status, "unresolved")
        self.assertIn("claim_id", record.correction_error)
        self.assertEqual(len(self.client.calls), 2)

    def test_uncertain_initial_or_recheck_is_not_passed(self):
        uncertain = {"status": "uncertain", "reasons": ["证据不足以判断"]}
        record = self.review(self.claim(), [uncertain])
        self.assertEqual(record.final_status, "uncertain")
        self.assertIsNone(record.corrected_claim)
        failed = {"status": "failed", "reasons": ["需要修改"]}
        record = self.review(self.claim(), [failed, self.dump(self.claim()), uncertain])
        self.assertEqual(record.final_status, "uncertain")
        self.assertEqual(record.recheck.status, "uncertain")

    def test_missing_path_text_cannot_be_marked_passed(self):
        record = self.review(self.claim(), [PASSED], paths=[])
        self.assertEqual(record.final_status, "uncertain")
        self.assertIn("KG 路径原文缺失", record.verification.reasons[0])

    def test_verification_api_and_format_failures_are_uncertain(self):
        truncated = replace(MockLLMClient().generate("mock"), finish_reason="length")
        for reply in (LLMClientError("离线模拟失败"), "not-json", truncated,
                      {"status": "unexpected", "reasons": []}, {"status": "failed", "reasons": []}):
            with self.subTest(reply=reply):
                record = self.review(self.claim(), [reply])
                self.assertEqual(record.final_status, "uncertain")
                self.assertIsNone(record.corrected_claim)
                self.assertEqual(len(self.client.calls), 1)

    def test_known_reference_error_survives_semantic_failure(self):
        record = self.review(self.claim(patient_fact_ids=["UNKNOWN"]),
                             [LLMClientError("核验失败"), LLMClientError("矫正失败")])
        self.assertEqual(record.verification.status, "failed")
        self.assertIn("患者事实编号不存在：UNKNOWN", record.verification.reasons)
        self.assertEqual(record.final_status, "uncertain")
        self.assertTrue(record.correction_error)

    def test_bad_correction_json_is_unresolved(self):
        record = self.review(self.claim(), [{"status": "failed", "reasons": ["需要修改"]}, "bad-json"])
        self.assertEqual(record.final_status, "unresolved")
        self.assertIsNone(record.recheck)
        self.assertTrue(record.correction_error)

    def test_pipeline_is_optional_reuses_paths_and_preserves_original_fields(self):
        claim = self.claim()
        payload = {"claims": [self.dump(claim)], "observation_match": ["旧字段原样保留"]}
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                client = ScriptedClient([payload, PASSED] if enabled else [payload])
                pipeline = KGRAGPipeline(ranker=self.ranker, client=client)
                with patch.object(self.ranker, "rank", wraps=self.ranker.rank) as rank:
                    result = pipeline.run("TEXT", "基底细胞癌", self.observation, top_k=100, enable_c4=enabled)
                self.assertEqual(rank.call_count, 1)
                self.assertEqual(result.claims, [claim])
                self.assertEqual(result.observation_match, payload["observation_match"])
                self.assertEqual(result_to_dict(result)["evidence_ledger"], self.dump(self.ledger))
                self.assertEqual(len(result.c4_results), int(enabled))
                self.assertEqual(len(client.calls), 2 if enabled else 1)
                restored = KGRAGResult(**json.loads(json.dumps(result_to_dict(result), ensure_ascii=False)))
                self.assertEqual(result_to_dict(restored), result_to_dict(result))
                if enabled:
                    context = json.loads(client.calls[1]["user"])
                    edge = context["kg_paths"]["PATH_TRI_031"][0]
                    original_edge = next(p for p in self.paths if p.path_id == "PATH_TRI_031").path.edges[0]
                    self.assertEqual(edge, original_edge.to_dict())
                    self.assertEqual(context["evidence_ledger"], self.dump(self.ledger))
                    self.assertTrue(client.calls[1]["json_mode"])
                old_payload = result_to_dict(result)
                old_payload.pop("c4_results")
                self.assertEqual(KGRAGResult(**old_payload).c4_results, [])

    def test_only_failed_claim_is_corrected_and_results_roundtrip(self):
        first = self.claim()
        second = self.claim(claim_id="CLAIM_002", claim_text="患者未提及瘙痒。",
                            patient_fact_ids=["TEXT:text:SYM_002"], kg_path_ids=[])
        corrected = self.claim(claim_id=second.claim_id, claim_text="患者明确否认瘙痒。",
                               patient_fact_ids=second.patient_fact_ids, kg_path_ids=[])
        failed = {"status": "failed", "reasons": ["absent 被误说成 missing"]}
        client = ScriptedClient([{"claims": [self.dump(first), self.dump(second)]},
                                 PASSED, failed, self.dump(corrected), PASSED])
        result = KGRAGPipeline(ranker=self.ranker, client=client).run(
            "TEXT", "基底细胞癌", self.observation, enable_c4=True,
        )
        self.assertEqual(result.claims, [first, second])
        self.assertEqual([r.final_status for r in result.c4_results], ["passed", "corrected"])
        self.assertIsNone(result.c4_results[0].corrected_claim)
        self.assertEqual(result.c4_results[1].corrected_claim, corrected)
        self.assertEqual(len(client.calls), 5)
        restored = KGRAGResult(**json.loads(json.dumps(result_to_dict(result))))
        self.assertEqual(restored.c4_results, result.c4_results)

    def test_empty_claims_do_not_trigger_c4_calls(self):
        client = ScriptedClient([{}])
        result = KGRAGPipeline(ranker=self.ranker, client=client).run(
            "TEXT", "基底细胞癌", self.observation, enable_c4=True,
        )
        self.assertEqual(result.c4_results, [])
        self.assertEqual(len(client.calls), 1)

    def test_no_paths_can_review_patient_only_claim(self):
        claim = self.claim(claim_text="患者报告出血。", kg_path_ids=[])
        client = ScriptedClient([{"claims": [self.dump(claim)]}, PASSED])
        with patch.object(self.ranker, "rank", return_value=([], [], 0)):
            result = KGRAGPipeline(ranker=self.ranker, client=client).run(
                "TEXT", "基底细胞癌", self.observation, enable_c4=True,
            )
        context = json.loads(client.calls[1]["user"])
        self.assertEqual(context["kg_paths"], {})
        self.assertTrue(context["evidence_ledger"]["patient_facts"])
        self.assertEqual(result.c4_results[0].final_status, "passed")

    def test_semantic_prompt_contains_state_role_and_scope_constraints(self):
        self.review(self.claim(), [PASSED])
        prompt = self.client.calls[0]["system"]
        for instruction in (
            "只核验当前 claim", "不将其他旧输出字段标记为已经核验",
            "编号存在不等于解释内容得到支持", "present 表示明确存在",
            "absent 表示明确不存在", "missing 表示未提供",
            "不得把 absent 说成存在或“未提及/未知”", "不得把 missing 说成存在或“没有/未见”",
            "每项患者陈述必须被其 patient_fact_ids 对应的事实覆盖",
            "引用 absent 本身合法", "BACKGROUND_ONLY 允许介绍疾病特点",
            "DIFFERENTIAL_ONLY 允许鉴别说明", "证据无法支持的医学描述",
            "不能靠模型自身医学知识补齐证据", "不代表医学上绝对正确",
        ):
            self.assertIn(instruction, prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
