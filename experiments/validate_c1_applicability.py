"""有限医学适用性修复的离线回归，不调用真实 API。

不相关路径摘要采自本轮修改前的工作区（已经包含病例编号隔离）。
仅排除本次明确允许变化的路径；检查所有患者事实、锚点及其他路径完整内容。
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.pad_case_input import build_pad_input
from experiments.validate_c1_pipeline_integration import MockLLMClient, RecordingRanker
from experiments.validate_c4_claim_verification import ScriptedClient, PASSED
from kg.path_ranker import EvidencePathRanker
from kg.path_retriever import path_restriction_reason
from rag.claim_verifier import reference_errors, review_claims
from rag.kg_rag_pipeline import KGRAGPipeline, build_structured_evidence_ledger
from rag.schemas import EvidenceClaim, KGRAGResult


UNCHANGED_HASHES = {
    'PAD_BCC_001|基底细胞癌': '72138b016b83ed55ebbac4a381f46bb558b7c7cf8f20477012ca0132c43cab67',
    'PAD_BCC_001|黑色素瘤': 'ee628b6621297d0ea327fbee4ab82262abf3a8be01e4f4e15424f88c0a0cae0f',
    'PAD_BCC_002|基底细胞癌': '91dafd1519dece36d6c8f98b6fbfbaafc1e3a4bb26ba5507ae9b0d18f50a659e',
    'PAD_BCC_002|黑色素瘤': '187e3cd8f454d2bb48a6cd5e7104ae99ee20a902c8efa9860edcff1699f9ccdc',
    'PAD_MEL_001|黑色素瘤': '4de7308b03f3408f7f3745c8e2df595931968421e4d0a5267636b589ac877b32',
    'PAD_MEL_001|黑色素细胞痣': 'c4fdef4fd9761c552e95fd0ca02f755f50a6f3806b65a2a9bd7be1bc50a093aa',
    'PAD_MEL_002|黑色素瘤': '5c60b4c40b453eef301aad6092b46f6ad981b181ad365fbb10b78ad6641330e3',
    'PAD_MEL_002|黑色素细胞痣': '28f57ae4159e7f9fea0d93c43febb9000d8608e273c3089a51d3137c714d4810',
    'PAD_NEV_001|黑色素细胞痣': 'b48a61aea41e77e6e3ffd2ed1e4ae52bd6000c9701c7201b8584e5896082a303',
    'PAD_NEV_001|黑色素瘤': '6276f19cd4d414068487b41bcf960b0565deb65cfee9980c73004e740c1d0110',
    'PAD_NEV_002|黑色素细胞痣': 'bcf3b4917d56730164671ed62aca0f20775075bf72246191e2208029318e5ac3',
    'PAD_NEV_002|黑色素瘤': '46b24cc7deec7da27f22e12244b53813c9668da735590848ce569a6f0b750257',
}


def unchanged_snapshot(anchors, paths, facts):
    retained = []
    for path in paths:
        if any(e.triple_id in {'TRI_006', 'TRI_013', 'TRI_030'} for e in path.path.edges):
            continue
        if path.path_id == 'PATH_TRI_034_TRI_062':
            continue
        p = path.to_dict()
        p.pop('rank')  # 有效性过滤会移动名次，但不能改变分数或相对顺序。
        for field in ('applicability_status', 'applicability_reason', 'applicability_sources'):
            p['role_profile'].pop(field)
        for edge in p['path']['edges']:
            edge.pop('applicability')
        retained.append(p)
    return {'anchors': [a.to_dict() for a in anchors], 'paths': retained,
            'facts': [asdict(f) for f in facts]}


class ApplicabilityTests(unittest.TestCase):
    def setUp(self):
        self.ranker = EvidencePathRanker()

    def rank(self, fields, disease='黑色素瘤'):
        return self.ranker.rank(disease, '', top_k=10000, max_hops=2, structured_fields=fields)[1]

    def test_six_cases_both_candidates_preserve_unrelated_evidence(self):
        for key, expected in UNCHANGED_HASHES.items():
            mother, disease = key.split('|')
            with self.subTest(case=mother, candidate=disease):
                p = build_pad_input(mother)
                anchors, paths, count = self.ranker.rank(disease, p['user_observation'],
                    top_k=10000, max_hops=2, structured_fields=p['structured_fields'])
                facts = self.ranker.anchor_mapper.extract_fact_records(p['user_observation'], mother,
                    structured_fields=p['structured_fields'])
                snapshot = unchanged_snapshot(anchors, paths, facts)
                self.assertEqual(hashlib.sha256(json.dumps(snapshot, ensure_ascii=False,
                    sort_keys=True).encode()).hexdigest(), expected)
                self.assertEqual(count, 34 if disease == '基底细胞癌' else 21)
                self.assertFalse(any(p.path_id in {'PATH_TRI_030', 'PATH_TRI_034_TRI_062'} for p in paths))
                for path in paths:
                    profile = path.role_profile
                    if 'differential_diagnosis' in path.relation_chain:
                        self.assertEqual(profile.claim_usage, 'DIFFERENTIAL_ONLY')
                    if any(e.triple_id in {'TRI_006', 'TRI_013'} for e in path.path.edges):
                        self.assertIn(profile.applicability_status, {'unknown', 'not_satisfied'})
                        self.assertNotEqual(profile.claim_usage, 'PATIENT_SUPPORT')
                        self.assertIn('population_context', profile.applicability_reason)

    def test_statistical_scope_has_three_states_for_both_sites(self):
        for tri, site, gender, opposite in [('TRI_006','BACK','MALE','FEMALE'),
                                            ('TRI_013','THIGH','FEMALE','MALE')]:
            for extra, state in [({}, 'unknown'), ({'gender': gender}, 'unknown'),
                                 ({'population_context':'NEW ZEALAND'}, 'unknown'),
                                 ({'gender':gender,'population_context':'UNKNOWN'}, 'unknown'),
                                 ({'gender':gender,'population_context':'OTHER'}, 'not_satisfied'),
                                 ({'gender':opposite,'population_context':'NEW ZEALAND'}, 'not_satisfied'),
                                 ({'gender':gender,'population_context':'NEW ZEALAND'}, 'satisfied')]:
                with self.subTest(triple=tri, fields=extra):
                    path = next(p for p in self.rank({'region':site, **extra}) if p.path_id == 'PATH_'+tri)
                    self.assertEqual(path.role_profile.applicability_status, state)
                    # THIGH 映射仍是 PARTIAL：条件满足不能绕过原可靠匹配要求。
                    expected = 'PATIENT_SUPPORT' if tri == 'TRI_006' and state == 'satisfied' else 'BACKGROUND_ONLY'
                    self.assertEqual(path.role_profile.claim_usage, expected)
                    self.assertFalse(path.role_profile.diagnosis_confirmed)
        # 直接按实体提供明确下肢事实，不改变原 PAD 映射。
        mapper = self.ranker.anchor_mapper
        anchors = mapper.extract_patient_facts('患者下肢有皮损。')
        raw = next(p for p in self.ranker.path_retriever.retrieve_paths('黑色素瘤') if p.path_id=='PATH_TRI_013')
        scored = self.ranker.score_path(raw, anchors, structured_fields={'gender':'FEMALE','population_context':'NEW ZEALAND'})
        self.assertEqual(scored.role_profile.claim_usage, 'PATIENT_SUPPORT')

    def test_satisfied_conditions_do_not_override_absent_or_missing(self):
        raw = next(p for p in self.ranker.path_retriever.retrieve_paths('黑色素瘤') if p.path_id=='PATH_TRI_006')
        for text in ['患者未见背部皮损。', '未提供背部信息。']:
            anchors = self.ranker.anchor_mapper.extract_patient_facts(text)
            result = self.ranker.score_path(raw, anchors,
                structured_fields={'gender':'MALE','population_context':'NEW ZEALAND'})
            self.assertEqual(result.role_profile.applicability_status, 'satisfied')
            self.assertEqual(result.role_profile.claim_usage, 'BACKGROUND_ONLY')

    def test_unverified_relation_is_filtered_not_disguised_as_background(self):
        retriever = self.ranker.path_retriever
        edge = next(e for e in retriever.edges if e.triple_id=='TRI_030')
        path = retriever._build_path(retriever.resolve_disease('基底细胞癌'), (edge,))
        self.assertIn('暂不作为有效证据', path_restriction_reason(path))
        with self.assertRaises(ValueError):
            self.ranker.score_path(path, self.ranker.anchor_mapper.extract('面部'))
        self.assertNotIn(path.path_id, [p.path_id for p in retriever.retrieve_one_hop_paths('基底细胞癌')])

    def test_only_incompatible_subtype_chain_is_blocked(self):
        r = self.ranker.path_retriever
        paths = r.retrieve_two_hop_paths('基底细胞癌')
        ids = {p.path_id for p in paths}
        self.assertNotIn('PATH_TRI_034_TRI_062', ids)
        self.assertIn('PATH_TRI_034_TRI_053', ids)
        self.assertIn('PATH_TRI_035_TRI_007', ids)
        self.assertIn('PATH_TRI_034', {p.path_id for p in r.retrieve_one_hop_paths('基底细胞癌')})
        self.assertIn('PATH_TRI_062', {p.path_id for p in r.retrieve_one_hop_paths('良性角化样病变')})
        edges = {e.triple_id:e for e in r.edges}
        blocked = r._build_path(r.resolve_disease('基底细胞癌'), (edges['TRI_034'],edges['TRI_062']))
        self.assertIn('亚类不兼容', path_restriction_reason(blocked))

    def test_blocked_paths_do_not_reach_model_or_c4_reference_pool(self):
        client = MockLLMClient()
        result = KGRAGPipeline(client=client).run('BCC_CHECK', '基底细胞癌',
            top_k=100, **build_pad_input('PAD_BCC_001'))
        for path_id in ['PATH_TRI_030', 'PATH_TRI_034_TRI_062']:
            self.assertNotIn(path_id, client.prompt)
            claim = EvidenceClaim(claim_id='CLAIM_001',claim_text='模拟无效路径引用',
                patient_fact_ids=[],kg_path_ids=[path_id])
            self.assertEqual(reference_errors(claim, result.evidence_ledger), [f'KG 路径编号不存在：{path_id}'])

    def test_c2_c3_c4_receive_limits_without_restoring_support(self):
        for mother in ['PAD_MEL_001','PAD_MEL_002']:
            with self.subTest(case=mother), patch('rag.kg_rag_pipeline.QwenLLMClient', side_effect=AssertionError('禁止真实API')):
                ranker, client = RecordingRanker(), MockLLMClient()
                result = KGRAGPipeline(ranker=ranker,client=client).run(mother+'_P0','黑色素瘤',
                    top_k=100, **build_pad_input(mother))
                ledger = result.evidence_ledger
                entry = next(p for p in ledger.paths if p.path_id=='PATH_TRI_006')
                self.assertEqual(entry.claim_usage,'BACKGROUND_ONLY')
                self.assertEqual(entry.matched_fact_ids,[])
                self.assertIn(entry.applicability_status, {'unknown','not_satisfied'})
                self.assertIn(entry.applicability_reason, client.prompt)
                self.assertIn('https://dermnetnz.org/topics/melanoma',client.prompt)
                region = next(f for f in ledger.patient_facts if f.source=='pad_ufes_20:region')
                claim = EvidenceClaim(claim_id='CLAIM_001',claim_text='患者部位有记录，但该人群统计不能直接用于患者支持。',
                    patient_fact_ids=[region.fact_id],kg_path_ids=[entry.path_id])
                c4 = ScriptedClient([PASSED])
                record = review_claims([claim],ledger,ranker.result[1],'黑色素瘤',result.user_observation,c4)[0]
                self.assertEqual(reference_errors(claim,ledger),[])
                self.assertEqual(record.original_claim,claim)
                self.assertEqual(json.loads(c4.calls[0]['user'])['evidence_ledger'],ledger.model_dump())
                self.assertNotIn(mother,client.prompt+c4.calls[0]['user'])
                restored = KGRAGResult(**json.loads(result.model_dump_json()))
                self.assertEqual(restored.evidence_ledger,ledger)


if __name__=='__main__':
    unittest.main(verbosity=2)
