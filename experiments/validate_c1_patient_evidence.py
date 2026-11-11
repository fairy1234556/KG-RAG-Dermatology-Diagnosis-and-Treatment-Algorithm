"""C1 离线回归：python experiments/validate_c1_patient_evidence.py。"""

from __future__ import annotations

import json
import sys
import unittest
from dataclasses import fields, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from kg.path_ranker import EvidencePathRanker, RankedEvidencePath
from rag.semantic_anchor import SemanticAnchor, SemanticAnchorMapper


class C1PatientEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mapper = SemanticAnchorMapper()
        cls.ranker = EvidencePathRanker()

    def facts(self, text="", **kwargs):
        return {
            fact.entity_id: fact
            for fact in self.mapper.extract_patient_facts(text, **kwargs)
        }

    def rank(self, text="", disease="基底细胞癌", **kwargs):
        return self.ranker.rank(disease, text, top_k=100, **kwargs)

    def direct(self, results, entity_id):
        return next(
            result for result in results
            if result.hop_count == 1 and result.end_entity_id == entity_id
        )

    def test_present_absent_missing_text(self):
        for text, expected in (
            ("患者出现出血", "present"),
            ("患者未见出血", "absent"),
            ("患者没有出血", "absent"),
            ("患者否认出血", "absent"),
            ("出血阴性", "absent"),
            ("患者仅有皮损", "missing"),
            ("患者未提供出血信息", "missing"),
            ("出血情况未提供", "missing"),
            ("是否出血不详", "missing"),
            ("不能排除出血", "missing"),
        ):
            with self.subTest(text=text):
                self.assertEqual(self.facts(text)["SYM_001"].fact_state, expected)
                anchors, results, _ = self.rank(text)
                result = self.direct(results, "SYM_001")
                self.assertEqual(result.role_profile.patient_fact_state, expected)
                matched = expected == "present"
                self.assertEqual("SYM_001" in {a.entity_id for a in anchors}, matched)
                self.assertEqual(bool(result.matched_anchor_ids), matched)
                self.assertEqual(result.entity_match_score > 0, matched)
                self.assertEqual(result.role_profile.claim_usage,
                                 "PATIENT_SUPPORT" if matched else "BACKGROUND_ONLY")

    def test_negated_itch_and_clause_scope(self):
        for text in ("患者没有瘙痒", "患者否认瘙痒", "瘙痒阴性"):
            with self.subTest(text=text):
                self.assertEqual(self.facts(text)["SYM_002"].fact_state, "absent")
                self.assertNotIn("SYM_002", {a.entity_id for a in self.mapper.extract(text)})
        for text in ("患者未见出血，但有瘙痒", "患者没有出血，伴瘙痒"):
            with self.subTest(text=text):
                facts = self.facts(text)
                self.assertEqual(facts["SYM_001"].fact_state, "absent")
                self.assertEqual(facts["SYM_002"].fact_state, "present")
        facts = self.facts("患者无出血及瘙痒")
        self.assertEqual(facts["SYM_001"].fact_state, "absent")
        self.assertEqual(facts["SYM_002"].fact_state, "absent")

    def test_conflicting_mentions_are_not_positive(self):
        text = "患者出血。患者否认出血。"
        self.assertFalse(self.facts(text)["SYM_001"].is_patient_match)
        self.assertEqual(self.mapper.extract(text), [])

    def test_english_negation_and_word_boundaries(self):
        facts = self.facts("No bleeding or itching")
        self.assertEqual(facts["SYM_001"].fact_state, "absent")
        self.assertEqual(facts["SYM_002"].fact_state, "absent")
        self.assertEqual(self.facts("Known bleeding")["SYM_001"].fact_state, "present")
        self.assertEqual(self.facts("bleeding not reported")["SYM_001"].fact_state, "missing")
        self.assertEqual({a.entity_id for a in self.mapper.extract("asymmetry")}, {"LF_003"})
        self.assertEqual(self.mapper.extract("background"), [])

    def test_pad_raw_boolean_values(self):
        values = (
            (True, "present"), ("True", "present"), (1, "present"),
            (False, "absent"), ("False", "absent"), (0, "absent"),
            (None, "missing"), ("", "missing"), ("UNK", "missing"),
            (float("nan"), "missing"), ("unknown", "missing"),
        )
        for value, expected in values:
            with self.subTest(value=value):
                facts = self.facts(structured_fields={"bleed": value, "itch": value})
                for entity_id in ("SYM_001", "SYM_002"):
                    self.assertEqual(facts[entity_id].fact_state, expected)
                    self.assertEqual(facts[entity_id].is_patient_match, expected == "present")
                _, results, _ = self.rank(structured_fields={"bleed": value})
                self.assertEqual(self.direct(results, "SYM_001").role_profile.patient_fact_state, expected)

    def test_raw_fields_override_rendered_observation(self):
        text = "患者出血、瘙痒及触痛，直径增大，面部皮损。"
        raw = {"bleed": False, "itch": None, "hurt": True, "grew": True, "region": "BACK"}
        anchors, results, _ = self.rank(text, structured_fields=raw)
        self.assertEqual({a.entity_id for a in anchors}, {"SITE_003"})
        self.assertEqual(self.direct(results, "SYM_001").role_profile.patient_fact_state, "absent")

    def test_fact_deletion_changes_role_but_keeps_kg(self):
        for before_text, before_raw, after_text, after_raw in (
            ("患者面部皮损伴出血", None, "患者面部皮损", None),
            ("", {"bleed": True, "region": "FACE"}, "", {"region": "FACE"}),
            # 原始字段删除后，不允许从旧生成文本恢复该患者事实。
            ("患者出血", {"bleed": True}, "患者出血", {}),
        ):
            with self.subTest(raw=before_raw):
                _, before, count_before = self.rank(before_text, structured_fields=before_raw)
                _, after, count_after = self.rank(after_text, structured_fields=after_raw)
                positive = self.direct(before, "SYM_001")
                removed = self.direct(after, "SYM_001")
                self.assertEqual(count_before, count_after)
                self.assertEqual(positive.path, removed.path)
                self.assertEqual(positive.role_profile.claim_usage, "PATIENT_SUPPORT")
                self.assertEqual(removed.role_profile.claim_usage, "BACKGROUND_ONLY")
                self.assertEqual(removed.role_profile.patient_fact_state, "missing")
                self.assertEqual(removed.matched_anchor_ids, ())
                self.assertEqual(removed.entity_match_score, 0)

    def test_partial_and_unmapped_fields_never_match(self):
        raw = {"hurt": True, "grew": True, "changed": True, "elevation": True, "region": "HAND"}
        facts = self.facts(structured_fields=raw)
        for entity_id in ("SYM_004", "LF_004"):
            self.assertEqual(facts[entity_id].fact_state, "present")
            self.assertFalse(facts[entity_id].mapping_reliable)
        self.assertEqual(self.mapper.extract("", structured_fields=raw), [])
        for disease, entity_id in (("光化性角化病", "SYM_004"), ("黑色素瘤", "LF_004")):
            with self.subTest(disease=disease):
                _, results, _ = self.rank(disease=disease, structured_fields=raw)
                result = self.direct(results, entity_id)
                self.assertEqual(result.role_profile.claim_usage, "BACKGROUND_ONLY")
                self.assertEqual(result.role_profile.patient_fact_state, "missing")
                self.assertEqual(result.entity_match_score, 0)
        self.assertEqual(self.mapper.extract("患者疼痛并有增长"), [])

    def test_mapping_table_controls_site_reliability(self):
        for region, expected in (("FACE", {"SITE_005"}), ("BACK", {"SITE_003"}),
                                 ("NOSE", set()), ("CHEST", set()), ("HAND", set())):
            with self.subTest(region=region):
                anchors = self.mapper.extract("", structured_fields={"region": region})
                self.assertEqual({a.entity_id for a in anchors}, expected)

    def test_general_kg_knowledge_is_not_patient_fact(self):
        anchors, results, _ = self.rank()
        self.assertEqual(anchors, [])
        for result in results:
            self.assertEqual(result.role_profile.patient_fact_state, "missing")
            self.assertEqual(result.role_profile.patient_alignment, "UNMATCHED")
            self.assertNotEqual(result.role_profile.claim_usage, "PATIENT_SUPPORT")
        for text in ("黑色素瘤通常伴有出血", "基底细胞癌可出现出血", "文献记载瘙痒"):
            self.assertFalse(any(a.entity_type == "Symptom" for a in self.mapper.extract(text)))

    def test_differential_paths_never_direct_support(self):
        _, results, _ = self.rank("患者出血，既往确诊黑色素瘤")
        matched_hops = set()
        for result in results:
            if "differential_diagnosis" not in result.relation_chain:
                continue
            self.assertEqual(result.role_profile.structural_role, "DIFFERENTIAL")
            self.assertEqual(result.role_profile.claim_usage, "DIFFERENTIAL_ONLY")
            if result.role_profile.patient_alignment == "MATCHED":
                matched_hops.add(result.hop_count)
        self.assertEqual(matched_hops, {1, 2})

    def test_match_does_not_confirm_diagnosis(self):
        _, results, _ = self.rank("患者出血并已接受皮肤镜检查")
        self.assertEqual(self.direct(results, "SYM_001").role_profile.claim_usage, "PATIENT_SUPPORT")
        self.assertEqual(self.direct(results, "EXAM_001").role_profile.claim_usage, "BACKGROUND_ONLY")
        for result in results:
            payload = json.loads(json.dumps(result.to_dict(), ensure_ascii=False))
            self.assertFalse(payload["role_profile"]["diagnosis_confirmed"])

    def test_score_path_rejects_nonpositive_or_unreliable_anchor(self):
        _, results, _ = self.rank("患者出血")
        path = self.direct(results, "SYM_001").path
        anchor = self.mapper.extract("患者出血")[0]
        for invalid in (replace(anchor, fact_state="absent"),
                        replace(anchor, fact_state="missing"),
                        replace(anchor, mapping_reliable=False)):
            result = self.ranker.score_path(path, [invalid])
            self.assertEqual(result.entity_match_score, 0)
            self.assertEqual(result.role_profile.claim_usage, "BACKGROUND_ONLY")

    def test_legacy_constructors_and_entity_filters(self):
        anchor = SemanticAnchor("SYM_001", "出血", "Symptom", "出血", "出血", "exact", 1.0, "standard_name_cn")
        self.assertTrue(anchor.is_patient_match)
        _, results, _ = self.rank("患者出血")
        result = self.direct(results, "SYM_001")
        legacy = {field.name: getattr(result, field.name) for field in fields(result) if field.name != "role_profile"}
        self.assertEqual(RankedEvidencePath(**legacy).role_profile.claim_usage, "BACKGROUND_ONLY")
        self.assertEqual({a.entity_id for a in self.mapper.extract("面部出血", {"Symptom"})}, {"SYM_001"})
        self.assertEqual(self.mapper.extract("出血", []), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
