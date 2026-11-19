"""六个 PAD 母病例的编号隔离回归；真实 C1/C2、模拟 C3/C4，无 API。

运行：python experiments/validate_patient_id_isolation.py
排序摘要已按必要适用性修复更新；修复前不相关路径的严格对照在
validate_c1_applicability.py 中保留。此处继续验证编号隔离和端到端引用。
模拟回答只验证引用与调用链，不证明模型的医学判断能力。
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pad_case_input import build_pad_input
from experiments.validate_c1_pipeline_integration import MockLLMClient, RecordingRanker
from rag.baseline_common import result_to_dict
from rag.claim_verifier import reference_errors
from rag.kg_rag_pipeline import KGRAGPipeline
from rag.schemas import KGRAGResult
from rag.semantic_anchor import SemanticAnchorMapper, model_case_id


BASELINE_HASHES = {'PAD_BCC_001': ('cc4b3a6017080f5bd6857174ad19ff2e1bdebdf8cff4ac44a63bad9dc523c21a',
                 'd7e234cb9b33343ed878f069355a3cb45be87b8c313ab9b86260107251fa5142'),
 'PAD_BCC_002': ('03ee9a70839a2195a416d2a957c7edfc946acb2d1288232fdcc50cee3c0dfc2b',
                 'd01c660e59ff06021e2997f48ba50ee8c80de8b5669d8d18bbabaa2652537c24'),
 'PAD_MEL_001': ('3b57d584077b7833a5c518103088368639f2c01916dac606a5fadd80ce2db255',
                 '8c69a57a0a8c8fca3ef53899593b7febf13a0635679dafe22b45f2a65bd96731'),
 'PAD_MEL_002': ('fecf2218bbbf88e740594e5663846b0cd32c4384c849186be3ac984c9556455e',
                 '3a17010951d5e667c8b9d17d879de221fd42c97fa8a027acebf811f51d0ed3e0'),
 'PAD_NEV_001': ('f005da403a24b69630e030e518536fc0c81a73a3f050eafd129acaecb7aaac02',
                 '9d8d551d4b1631cefae2afa84b0c77b8aab8e50396c8ac68ce60f344da2b2f63'),
 'PAD_NEV_002': ('83322afe4926c4c87702fb42166f4c96d0c93b2f5542a30c6f7f0f1b88224327',
                 '99288bd227d978613b1017ec2048329e21e12aef84f422b4209f4cb6e226f425')}
STATE_COUNTS = {
    "PAD_BCC_001": (8, 1, 0), "PAD_BCC_002": (6, 3, 0),
    "PAD_MEL_001": (7, 2, 0), "PAD_MEL_002": (6, 3, 0),
    "PAD_NEV_001": (3, 5, 1), "PAD_NEV_002": (4, 5, 0),
}


class CapturingClient(MockLLMClient):
    """从真实提示词读取编号并回显，绝不自行拼接研究 ID。"""

    def __init__(self, correct_once=False):
        self.calls = []
        self.correct_once = correct_once
        self.verifications = 0

    def generate(self, user_prompt, system_prompt=None, json_mode=False):
        self.calls.append((user_prompt, system_prompt))
        if "【C2 结构化证据台账】\n" in user_prompt:
            tail = user_prompt.split("【C2 结构化证据台账】\n", 1)[1]
            self.ledger = json.JSONDecoder().raw_decode(tail)[0]
            region = next(f for f in self.ledger["patient_facts"] if f["source"] == "pad_ufes_20:region")
            linked = [p["path_id"] for p in self.ledger["paths"] if region["fact_id"] in p["matched_fact_ids"]]
            reply = {"claims": [{
                "claim_id": "CLAIM_001", "claim_text": "已记录患者的皮损部位，不能据此确诊。",
                "patient_fact_ids": [region["fact_id"]], "kg_path_ids": linked[:1],
            }]}
        else:
            payload = json.loads(user_prompt)
            if "problems" in payload:
                reply = {**payload["claim"], "claim_text": "患者部位有记录，证据仍不足以确诊。"}
            else:
                self.verifications += 1
                reply = ({"status": "failed", "reasons": ["离线流程测试：要求改写表述。"]}
                         if self.correct_once and self.verifications == 1
                         else {"status": "passed", "reasons": []})
        return replace(super().generate(user_prompt, system_prompt, json_mode),
                       content=json.dumps(reply, ensure_ascii=False))


class PatientIdIsolationTests(unittest.TestCase):
    def setUp(self):
        guard = patch("rag.kg_rag_pipeline.QwenLLMClient", side_effect=AssertionError("禁止真实 API"))
        guard.start()
        self.addCleanup(guard.stop)

    def test_six_cases_both_candidates_and_all_model_requests(self):
        with (ROOT / "experiments/cases/pad_pilot_mother_cases_v1.csv").open() as stream:
            cases = list(csv.DictReader(stream))
        self.assertEqual({r["mother_case_id"] for r in cases}, set(BASELINE_HASHES))
        all_fact_ids = set()
        for row in cases:
            mother = row["mother_case_id"]
            original = build_pad_input(mother)
            correct = {"BCC": "基底细胞癌", "MEL": "黑色素瘤", "NEV": "黑色素细胞痣"}[row["diagnostic"]]
            # 仅为已有 KG 鉴别关系的确定性输入检查，不宣称病例级医学合理性已获确认。
            alternative = "黑色素细胞痣" if row["diagnostic"] == "MEL" else "黑色素瘤"
            previous_ids = None
            for index, disease in enumerate((correct, alternative)):
                with self.subTest(case=mother, candidate=disease):
                    ranker = RecordingRanker()
                    client = CapturingClient(correct_once=bool(index))
                    result = KGRAGPipeline(ranker=ranker, client=client).run(
                        mother + "_P0", disease, top_k=10000, enable_c4=True, **original,
                    )
                    self.assertEqual(result.user_observation, original["user_observation"])
                    self.assertEqual(result.candidate_disease, disease)
                    self.assertEqual(ranker.received["structured_fields"], original["structured_fields"])
                    facts = result.evidence_ledger.patient_facts
                    counts = Counter(f.fact_state for f in facts)
                    self.assertEqual(tuple(counts[s] for s in ("present", "absent", "missing")), STATE_COUNTS[mother])
                    self.assertEqual(sum(f.mapping_reliable for f in facts), 3)
                    for fact in facts:
                        field = fact.source.split(":")[-1]
                        self.assertEqual(fact.fact_text, f"{field}={row[field]}")
                        expected_state = ("missing" if not row[field] else
                                          "absent" if row[field] == "False" else "present")
                        self.assertEqual(fact.fact_state, expected_state)
                        expected_entity = {"itch": "SYM_002", "bleed": "SYM_001", "hurt": "SYM_004",
                                           "grew": "LF_004", "region": "SITE_005" if row["region"] == "FACE" else "SITE_003"}.get(field)
                        self.assertEqual(fact.entity_id, expected_entity)
                        self.assertEqual(fact.mapping_reliable, field in {"itch", "bleed", "region"})
                    ids = {f.fact_id for f in facts}
                    self.assertEqual(len(ids), 9)
                    if previous_ids is None:
                        self.assertTrue(ids.isdisjoint(all_fact_ids))
                        all_fact_ids.update(ids)
                    else:
                        self.assertEqual(ids, previous_ids)
                    previous_ids = ids
                    anchors, paths, count = ranker.result
                    for entry, path in zip(result.evidence_ledger.paths, paths):
                        self.assertEqual(entry.path_id, path.path_id)
                        self.assertEqual(entry.triple_ids, [edge.triple_id for edge in path.path.edges])
                        self.assertEqual(entry.claim_usage, path.role_profile.claim_usage)
                        self.assertEqual(entry.matched_fact_ids, [
                            f.fact_id for f in facts if f.fact_state == "present" and f.mapping_reliable
                            and path.role_profile.applicability_status in {"not_required", "satisfied"}
                            and f.entity_id in path.matched_anchor_ids
                        ])
                    snapshot = {"anchors": [a.to_dict() for a in anchors],
                                "paths": [p.to_dict() for p in paths], "count": count}
                    fingerprint = hashlib.sha256(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
                    self.assertEqual(fingerprint, BASELINE_HASHES[mother][index])
                    payload = result_to_dict(result)
                    self.assertEqual(client.ledger, payload["evidence_ledger"])
                    self.assertEqual(result.case_id_mapping, {model_case_id(mother): mother})
                    self.assertEqual(result.case_id, mother + "_P0")
                    self.assertEqual(result_to_dict(KGRAGResult(**json.loads(json.dumps(payload)))), payload)
                    self.assertEqual(reference_errors(result.claims[0], result.evidence_ledger), [])
                    review = result.c4_results[0]
                    self.assertEqual(review.final_status, "corrected" if index else "passed")
                    self.assertEqual(len(client.calls), 4 if index else 2)
                    if index:
                        self.assertEqual(review.corrected_claim.patient_fact_ids, result.claims[0].patient_fact_ids)
                        self.assertEqual(review.corrected_claim.claim_id, result.claims[0].claim_id)
                        self.assertEqual(reference_errors(review.corrected_claim, result.evidence_ledger), [])
                    for user, system in client.calls:
                        visible = user + (system or "")
                        self.assertNotRegex(visible, r"PAD_(?:BCC|MEL|NEV)_\d+")
                        self.assertNotIn(row["patient_id"], visible)
                        for forbidden in ("diagnostic", "mother_case_id", "patient_id", "lesion_id",
                                          "candidate_score", "positive_evidence", "case_id_mapping", "biopsed"):
                            self.assertNotIn(forbidden, visible)
                        self.assertIn(model_case_id(mother), user)
            self.assertEqual(build_pad_input(mother), original)
        self.assertEqual(len(all_fact_ids), 54)

    def test_identity_is_stable_across_intervention_and_text_entry(self):
        mapper = SemanticAnchorMapper()
        for mother in BASELINE_HASHES:
            states = []
            ids = []
            for fields in ({"bleed": True}, {"bleed": False}, {}):
                facts = mapper.extract_fact_records("患者出血。", mother, structured_fields=fields)
                bleed = next(f for f in facts if f.source == "pad_ufes_20:bleed")
                states.append(bleed.fact_state)
                ids.append(bleed.fact_id)
            self.assertEqual(states, ["present", "absent", "missing"])
            self.assertEqual(len(set(ids)), 1)
            text_fact = mapper.extract_fact_records("患者出血。", mother)[0]
            self.assertEqual(text_fact.fact_id, model_case_id(mother) + ":text:SYM_001")
            self.assertNotIn(mother, text_fact.fact_id)
        self.assertEqual(model_case_id(" PAD_BCC_001 "), model_case_id("PAD_BCC_001"))
        with self.assertRaises(ValueError):
            model_case_id(" ")

    def test_legacy_result_without_mapping_still_loads(self):
        result = KGRAGPipeline(client=MockLLMClient()).run("OLD", "基底细胞癌", "患者出血。")
        payload = result_to_dict(result)
        payload.pop("case_id_mapping")
        self.assertEqual(KGRAGResult(**payload).case_id_mapping, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
