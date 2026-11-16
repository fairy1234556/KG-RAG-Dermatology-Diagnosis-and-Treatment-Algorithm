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

    def test_unsupported_exclusion_from_absent_fact_enters_targeted_correction(self):
        # 固定真实失败案例；预设回答仅证明提示词传递及流程，不证明真实模型能发现错误。
        original = self.claim(
            claim_text="患者明确否认瘙痒症状，这有助于排除部分伴有剧烈瘙痒的炎症性或过敏性皮肤病，"
                       "但不能单独用于确诊或排除基底细胞癌。",
            patient_fact_ids=["TEXT:text:SYM_002"], kg_path_ids=[],
        )
        corrected = self.claim(
            claim_text="患者明确否认瘙痒症状；现有证据不足以据此作出疾病排除结论。",
            patient_fact_ids=original.patient_fact_ids, kg_path_ids=[],
        )
        reason = "‘有助于排除部分伴有剧烈瘙痒的炎症性或过敏性皮肤病’缺少 KG 证据，瘙痒 absent 事实不能单独支持该推断。"
        self.assertEqual(reference_errors(original, self.ledger), [])
        fact = next(f for f in self.ledger.patient_facts if f.fact_id == original.patient_fact_ids[0])
        self.assertEqual(fact.fact_state, "absent")
        record = self.review(original, [{"status": "failed", "reasons": [reason]},
                                       self.dump(corrected), PASSED])
        verification_call, correction_call, recheck_call = self.client.calls
        for instruction in (
            "必须分别核验患者事实描述和由该事实推导的医学结论",
            "单一症状的存在或不存在，不能在缺少适用 KG 证据时用于确认、排除疾病",
            "“有助于排除”“提示更可能”等弱化表述仍是医学推断",
            "属于无依据推断，应返回 failed", "在 reasons 中指出具体推断片段及缺少的证据依据",
            "句末附加“不能单独确诊或排除”也不能抵消前文缺乏依据的推断",
        ):
            self.assertIn(instruction, verification_call["system"])
        self.assertIn("保留正确的患者事实及其 patient_fact_ids", correction_call["system"])
        self.assertIn("只删除该推断或改为证据不足的表述", correction_call["system"])
        self.assertEqual(json.loads(verification_call["user"])["claim"], self.dump(original))
        self.assertEqual(json.loads(correction_call["user"])["problems"], [reason])
        self.assertEqual(json.loads(recheck_call["user"])["claim"], self.dump(corrected))
        self.assertEqual(record.verification.status, "failed")
        self.assertEqual(record.original_claim, original)
        self.assertEqual(record.corrected_claim, corrected)
        self.assertEqual(record.corrected_claim.claim_id, original.claim_id)
        self.assertEqual(record.corrected_claim.patient_fact_ids, original.patient_fact_ids)
        self.assertEqual(record.recheck.status, "passed")
        self.assertEqual(record.final_status, "corrected")
        self.assertEqual(len(self.client.calls), 3)

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

    def test_recheck_accepts_omission_and_truthful_ledger_gap_statement(self):
        # 固定样例只验证范围约束的传递和流程，不证明真实模型会遵守提示词。
        original = self.claim(claim_text="患者面部出现结节并伴出血。",
                              patient_fact_ids=["TEXT:text:SITE_005", "TEXT:text:SYM_001"])
        corrected = self.claim(
            claim_text="患者报告的部位为面部，并伴有出血。当前台账未登记结节事实，故不将其作为论证依据。",
            patient_fact_ids=original.patient_fact_ids,
        )
        self.assertEqual({f.entity_id for f in self.ledger.patient_facts},
                         {"SITE_005", "SYM_001", "SYM_002"})
        failed = {"status": "failed", "reasons": ["结节作为患者事实直接论证，但未登记对应事实编号。"]}
        record = self.review(original, [failed, self.dump(corrected), PASSED])
        self.assertEqual(record.final_status, "corrected")
        self.assertEqual(record.recheck.status, "passed")
        self.assertEqual(record.original_claim, original)
        self.assertEqual(record.corrected_claim, corrected)
        for call in (self.client.calls[0], self.client.calls[2]):
            for instruction in (
                "只核验当前 claim 实际陈述的内容，不要求每条 claim 覆盖原始患者观察的全部信息",
                "某个特征没有在当前 claim 中陈述，不构成遗漏或引用不完整",
                "若 claim 仅说明", "应核对台账是否确实缺少该记录",
                "不应因此再次判为引用不完整，也不得要求补造 fact_id",
            ):
                self.assertIn(instruction, call["system"])
        self.assertEqual(json.loads(self.client.calls[2]["user"])["claim"], self.dump(corrected))
        # 只陈述出血、或如实说明台账范围，都无需覆盖原始观察中的所有特征。
        for claim in (self.claim(claim_text="患者报告出血。", kg_path_ids=[]), corrected):
            with self.subTest(text=claim.claim_text):
                self.assertEqual(reference_errors(claim, self.ledger), [])
                result = self.review(claim, [PASSED])
                self.assertEqual(result.final_status, "passed")
                self.assertIsNone(result.corrected_claim)
                self.assertEqual(len(self.client.calls), 1)

    def test_correction_keeps_existing_melanoma_and_keratosis_evidence_separate(self):
        path_ids = ["PATH_TRI_035_TRI_007", "PATH_TRI_034_TRI_053", "PATH_TRI_034_TRI_054"]
        original = self.claim(
            claim_text="患者报告出血；黑色素瘤和良性角化样病变均可能出血，因此直接支持基底细胞癌。",
            kg_path_ids=path_ids,
        )
        corrected = self.claim(
            claim_text="患者报告出血。图谱显示黑色素瘤可能出血；良性角化样病变可表现为蜡样或疣状表面、"
                       "贴附样丘疹或斑块。这些知识仅用于鉴别，不能作为基底细胞癌的直接支持。",
            kg_path_ids=path_ids,
        )
        reason = "良性角化样病变的外观证据不能扩展为出血证据；鉴别证据不能当作基底细胞癌的直接支持。"
        record = self.review(original, [{"status": "failed", "reasons": [reason]},
                                       self.dump(corrected), PASSED])
        self.assertEqual(record.final_status, "corrected")
        self.assertEqual(record.corrected_claim, corrected)
        self.assertEqual(record.recheck.status, "passed")
        self.assertEqual(len(self.client.calls), 3)
        correction_call = self.client.calls[1]
        for instruction in (
            "矫正前必须根据实际 kg_paths 逐条核对内容",
            "不能仅依据问题原因就断言某条 KG 证据不存在",
            "不得错误否定已有证据", "“证据存在但用途受限”不等于“证据不存在”",
            "黑色素瘤出血与良性角化样病变的外观特征必须分别判断",
        ):
            self.assertIn(instruction, correction_call["system"])
        # 核对真实 KG 内容确实传给核验、矫正和复核，不能只靠模拟回答声称保留了证据。
        for call in self.client.calls:
            context = json.loads(call["user"])
            melanoma = context["kg_paths"][path_ids[0]][1]
            self.assertEqual((melanoma["triple_id"], melanoma["head_name"], melanoma["tail_name"]),
                             ("TRI_007", "黑色素瘤", "出血"))
            self.assertIn("出血", melanoma["evidence_text"])
            for path_id, triple_id, feature in ((path_ids[1], "TRI_053", "蜡样或疣状表面"),
                                                 (path_ids[2], "TRI_054", "贴附样丘疹或斑块")):
                edge = context["kg_paths"][path_id][1]
                self.assertEqual((edge["triple_id"], edge["head_name"], edge["tail_name"]),
                                 (triple_id, "良性角化样病变", feature))
            roles = {p["path_id"]: p["claim_usage"] for p in context["evidence_ledger"]["paths"]}
            self.assertTrue(all(roles[path_id] == "DIFFERENTIAL_ONLY" for path_id in path_ids))

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

    def test_string_reasons_remain_unchanged_and_allow_correction(self):
        reasons = ["结节未登记，证据引用不完整。", "不能用出血编号代替结节事实。"]
        record = self.review(self.claim(), [{"status": "failed", "reasons": reasons},
                                           self.dump(self.claim()), PASSED])
        self.assertEqual(record.verification.reasons, reasons)
        self.assertEqual(record.final_status, "corrected")
        self.assertEqual(json.loads(self.client.calls[1]["user"])["problems"], reasons)

    def test_object_reasons_are_preserved_and_enter_correction(self):
        reasons = [{
            "fragment": "患者面部出现结节", "reason": "结节未登记，证据引用不完整。",
            "evidence_ids": ["TEXT:text:SITE_005", "TEXT:text:SYM_001"],
            "detail": "不能认定患者没有结节。",
        }]
        original = self.claim(claim_text="患者面部出现结节并伴出血。")
        record = self.review(original, [{"status": "failed", "reasons": reasons},
                                       self.dump(self.claim()), PASSED])
        self.assertEqual(record.verification.status, "failed")
        self.assertEqual(record.final_status, "corrected")
        self.assertEqual(record.original_claim, original)
        self.assertEqual(record.corrected_claim.claim_id, original.claim_id)
        readable = record.verification.reasons[0]
        for text in ("问题片段：患者面部出现结节", "原因：结节未登记，证据引用不完整。",
                     "证据编号：", "TEXT:text:SITE_005", "TEXT:text:SYM_001",
                     "detail：不能认定患者没有结节。"):
            self.assertIn(text, readable)
        self.assertEqual(json.loads(self.client.calls[1]["user"])["problems"], [readable])
        self.assertEqual(len(self.client.calls), 3)
        self.assertTrue(all(isinstance(reason, str) for reason in self.dump(record)["verification"]["reasons"]))

    def test_mixed_and_nested_reason_fields_are_not_discarded(self):
        reasons = ["证据存在歧义。", {
            "fragment": "该表现支持候选疾病", "explanation": "支持范围无法确定。",
            "details": {"limitation": "缺少检查结果", "evidence": ["PATH_TRI_031"]},
        }]
        record = self.review(self.claim(), [{"status": "uncertain", "reasons": reasons}])
        self.assertEqual(record.verification.status, "uncertain")
        self.assertEqual(record.verification.reasons[0], reasons[0])
        self.assertIn("说明：支持范围无法确定。", record.verification.reasons[1])
        self.assertIn(json.dumps(reasons[1]["details"], ensure_ascii=False), record.verification.reasons[1])
        self.assertNotIn("语义核验未完成", "".join(record.verification.reasons))
        self.assertEqual(len(self.client.calls), 1)

    def test_object_reasons_are_also_parsed_during_recheck(self):
        failed = {"status": "failed", "reasons": [{"reason": "仍然超出证据范围。"}]}
        record = self.review(self.claim(), [failed, self.dump(self.claim()), failed])
        self.assertEqual(record.final_status, "unresolved")
        self.assertEqual(record.recheck.status, "failed")
        self.assertEqual(record.recheck.reasons, ["原因：仍然超出证据范围。"])
        self.assertEqual(len(self.client.calls), 3)

    def test_unparseable_reasons_are_uncertain_even_if_model_says_passed(self):
        invalid_values = [None, "不是列表", {"reason": "不是列表"}, [None], [123], [" "],
                          [{}], [{"reason": " "}], [{"confidence": 0.9}],
                          [{"evidence_ids": ["PATH_TRI_031"]}], ["实际错误原因不可丢失", {}]]
        for status in ("passed", "failed"):
            for reasons in invalid_values:
                with self.subTest(status=status, reasons=reasons):
                    record = self.review(self.claim(), [{"status": status, "reasons": reasons}])
                    self.assertEqual(record.final_status, "uncertain")
                    self.assertIn("语义核验未完成", record.verification.reasons[0])
                    self.assertIn(json.dumps(reasons, ensure_ascii=False), record.verification.reasons[0])
                    self.assertIsNone(record.corrected_claim)
                    self.assertEqual(len(self.client.calls), 1)

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
