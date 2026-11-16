"""C2 离线验收：python experiments/validate_c2_evidence_ledger.py。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pad_case_input import build_pad_input
from experiments.validate_c1_pipeline_integration import MockLLMClient, RecordingRanker
from rag.kg_rag_pipeline import KGRAGPipeline, format_evidence_ledger
from rag.schemas import KGRAGResult


def dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


class C2EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        guard = patch("rag.kg_rag_pipeline.QwenLLMClient", side_effect=AssertionError("禁止真实 API"))
        guard.start()
        self.addCleanup(guard.stop)
        self.ranker = RecordingRanker()
        self.client = MockLLMClient()
        self.pipeline = KGRAGPipeline(ranker=self.ranker, client=self.client)

    def run_case(self, fields, mother="PAD_BCC_001", condition="P0", disease="基底细胞癌"):
        return self.pipeline.run(
            case_id=f"{mother}_{condition}", candidate_disease=disease,
            user_observation="旧文本：患者出血及触痛，直径增大。",
            structured_fields=fields, mother_case_id=mother, top_k=100,
        )

    @staticmethod
    def fact(result, field, mother="PAD_BCC_001"):
        return next(f for f in result.evidence_ledger.patient_facts if f.fact_id == f"{mother}:{field}")

    def test_stable_ids_same_case_and_field(self):
        first = self.run_case({"bleed": True, "itch": True})
        again = self.run_case({"itch": True, "bleed": True}, condition="P1")
        self.assertEqual(dump(first.evidence_ledger), dump(again.evidence_ledger))
        ids = [f.fact_id for f in first.evidence_ledger.patient_facts]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("PAD_BCC_001:bleed", ids)
        self.assertIn("PAD_BCC_001:itch", ids)

    def test_different_cases_have_different_fact_ids(self):
        one = self.run_case({"bleed": True})
        two = self.run_case({"bleed": True}, mother="PAD_BCC_002")
        a, b = self.fact(one, "bleed"), self.fact(two, "bleed", "PAD_BCC_002")
        self.assertNotEqual(a.fact_id, b.fact_id)
        self.assertEqual(a.entity_id, b.entity_id)

    def test_present_fact_links_to_direct_path_and_prompt(self):
        result = self.run_case({"bleed": True})
        fact = self.fact(result, "bleed")
        self.assertEqual((fact.entity_id, fact.fact_state, fact.mapping_reliable), ("SYM_001", "present", True))
        self.assertEqual(fact.source, "pad_ufes_20:bleed")
        direct = next(p for p in result.evidence_ledger.paths if p.path_id == "PATH_TRI_031")
        self.assertEqual(direct.triple_ids, ["TRI_031"])
        self.assertEqual(direct.matched_fact_ids, [fact.fact_id])
        self.assertEqual(direct.claim_usage, "PATIENT_SUPPORT")
        self.assertIn('matched_fact_ids=["PAD_BCC_001:bleed"]', self.client.prompt)
        self.assertIn("fact_id=PAD_BCC_001:bleed", self.client.prompt)

    def test_absent_and_missing_are_retained_without_positive_links(self):
        for fields, state in (({"bleed": False}, "absent"), ({}, "missing")):
            with self.subTest(state=state):
                result = self.run_case(fields)
                fact = self.fact(result, "bleed")
                self.assertEqual(fact.fact_state, state)
                self.assertFalse(any(fact.fact_id in p.matched_fact_ids for p in result.evidence_ledger.paths))
                self.assertNotIn("旧文本", self.client.prompt)

    def test_one_and_two_hop_triple_ids_are_complete_and_ordered(self):
        result = self.run_case({"bleed": True})
        originals = {p.path_id: p for p in self.ranker.result[1]}
        self.assertEqual({p.hop_count for p in originals.values()}, {1, 2})
        for entry in result.evidence_ledger.paths:
            original = originals[entry.path_id]
            self.assertEqual(entry.triple_ids, [e.triple_id for e in original.path.edges])
            self.assertEqual(len(entry.triple_ids), original.hop_count)
            self.assertEqual(entry.claim_usage, original.role_profile.claim_usage)
        two = next(p for p in result.evidence_ledger.paths if p.path_id == "PATH_TRI_035_TRI_007")
        self.assertEqual(two.triple_ids, ["TRI_035", "TRI_007"])

    def test_deleting_fact_removes_old_links_on_reused_pipeline(self):
        before = self.run_case({"bleed": True, "itch": True})
        after = self.run_case({"itch": True}, condition="P1")
        self.assertTrue(any("PAD_BCC_001:bleed" in p.matched_fact_ids for p in before.evidence_ledger.paths))
        self.assertFalse(any("PAD_BCC_001:bleed" in p.matched_fact_ids for p in after.evidence_ledger.paths))
        self.assertEqual(self.fact(after, "bleed").fact_state, "missing")
        self.assertEqual(self.fact(before, "bleed").fact_state, "present")
        self.assertEqual(dump(self.fact(before, "itch")), dump(self.fact(after, "itch")))

    def test_partial_and_unmapped_facts_are_not_lost_or_matched(self):
        result = self.run_case({"hurt": True, "grew": True, "changed": True, "elevation": False, "region": "NOSE"})
        for field in ("hurt", "grew", "changed", "region"):
            fact = self.fact(result, field)
            self.assertEqual(fact.fact_state, "present")
            self.assertFalse(fact.mapping_reliable)
        self.assertIsNone(self.fact(result, "changed").entity_id)
        self.assertEqual(self.fact(result, "elevation").fact_state, "absent")
        self.assertTrue(all(not p.matched_fact_ids for p in result.evidence_ledger.paths))

    def test_matched_differential_paths_keep_role(self):
        result = self.pipeline.run("TEXT", "基底细胞癌", "患者出血，既往确诊黑色素瘤", top_k=100)
        originals = {p.path_id: p for p in self.ranker.result[1]}
        hops = set()
        for entry in result.evidence_ledger.paths:
            path = originals[entry.path_id]
            if "differential_diagnosis" in path.relation_chain:
                self.assertEqual(entry.claim_usage, "DIFFERENTIAL_ONLY")
                if entry.matched_fact_ids:
                    hops.add(path.hop_count)
        self.assertEqual(hops, {1, 2})

    def test_result_file_roundtrip_preserves_all_ids_and_roles(self):
        result = self.run_case({"bleed": True, "itch": False})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.json"
            path.write_text(json.dumps(dump(result), ensure_ascii=False), encoding="utf-8")
            restored = KGRAGResult(**json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(dump(result), dump(restored))
        facts = {f.fact_id: f for f in restored.evidence_ledger.patient_facts}
        for entry in restored.evidence_ledger.paths:
            for fact_id in entry.matched_fact_ids:
                self.assertEqual(facts[fact_id].fact_state, "present")
                self.assertTrue(facts[fact_id].mapping_reliable)

    def test_pad_entry_identity_and_legacy_output_compatibility(self):
        inputs = build_pad_input("PAD_BCC_001", ["bleed"])
        result = self.pipeline.run("PAD_BCC_001_P1", "基底细胞癌", top_k=100, **inputs)
        self.assertEqual(self.fact(result, "bleed").fact_state, "missing")
        self.assertNotIn("PAD_BCC_001", result.user_observation)
        self.assertTrue(result.evidence_paths)
        legacy_text = format_evidence_ledger(self.ranker.result[1])
        self.assertIn("【患者匹配支持证据】", legacy_text)
        self.assertNotIn("matched_fact_ids=", legacy_text)
        payload = dump(result)
        payload.pop("evidence_ledger")
        self.assertEqual(KGRAGResult(**payload).evidence_ledger.paths, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
