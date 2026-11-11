"""C1 完整调用链验收：真实 KG/排序/C2 台账 + 模拟模型，无 API 请求。"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments import run_pad_rq1_pilot, run_pad_rq2_pilot
from experiments.pad_case_input import build_pad_input
from kg.path_ranker import EvidencePathRanker
from rag.kg_rag_pipeline import KGRAGPipeline, format_pad_observation
from rag.llm_client import LLMResult


class RecordingRanker(EvidencePathRanker):
    def rank(self, *args, **kwargs):
        self.received = kwargs
        self.result = super().rank(*args, **kwargs)
        return self.result


class MockLLMClient:
    def generate(self, user_prompt, system_prompt=None, json_mode=False):
        self.prompt = user_prompt
        self.json_mode = json_mode
        return LLMResult(
            content="{}", model="mock", provider="offline-test", prompt_version="test",
            finish_reason="stop", request_id="mock-c1", prompt_tokens=0,
            completion_tokens=0, total_tokens=0, latency_seconds=0,
            temperature=0, max_completion_tokens=100, enable_thinking=False, seed=42,
        )


class C1PipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        # 入口若漏注入模拟客户端，立即失败，不能意外调用真实 API。
        guard = patch("rag.kg_rag_pipeline.QwenLLMClient", side_effect=AssertionError("禁止真实 API"))
        guard.start()
        self.addCleanup(guard.stop)
        self.ranker = RecordingRanker()
        self.client = MockLLMClient()
        self.pipeline = KGRAGPipeline(ranker=self.ranker, client=self.client)

    @staticmethod
    def patient_section(prompt):
        return prompt.split("三、用户观察\n", 1)[1].split("\n\n四、", 1)[0]

    def test_bleeding_states_reach_ranker_prompt_and_ledger(self):
        stale_text = "旧文本标记：患者持续出血，面部有触痛和直径增大。"
        for raw, state, sentence in (
            ({"bleed": True}, "present", "患者存在出血。"),
            ({"bleed": False}, "absent", "患者未见出血。"),
            ({}, "missing", "未提供出血信息。"),
        ):
            with self.subTest(state=state):
                result = self.pipeline.run("C1_TEST", "基底细胞癌", stale_text,
                                           top_k=100, structured_fields=raw)
                self.assertEqual(self.ranker.received["structured_fields"], raw)
                self.assertIsNot(self.ranker.received["structured_fields"], raw)
                anchors, paths, _ = self.ranker.result
                direct = next(p for p in paths if p.hop_count == 1 and p.end_entity_id == "SYM_001")
                expected_usage = "PATIENT_SUPPORT" if state == "present" else "BACKGROUND_ONLY"
                self.assertEqual(direct.role_profile.patient_fact_state, state)
                self.assertEqual(direct.role_profile.claim_usage, expected_usage)
                self.assertEqual(bool(direct.matched_anchor_ids), state == "present")
                self.assertEqual("SYM_001" in {a.entity_id for a in anchors}, state == "present")
                observation = self.patient_section(self.client.prompt)
                self.assertEqual(observation, result.user_observation)
                self.assertEqual(observation, self.ranker.received["observation_text"])
                self.assertIn(sentence, observation)
                self.assertNotIn("旧文本标记", self.client.prompt)
                self.assertNotIn("触痛", observation)
                self.assertNotIn("直径增大", observation)
                ledger = self.client.prompt.split("【证据角色账本】", 1)[1].split("【Top-k", 1)[0]
                title = "【患者匹配支持证据】" if state == "present" else "【疾病背景知识】"
                group = ledger.split(title, 1)[1].split("【", 1)[0]
                self.assertIn(f"path_id={direct.path_id}；", group)
                self.assertIn(f"允许用途={expected_usage}", group)
                self.assertTrue(self.client.json_mode)
                self.assertEqual(result.run_status, "success")

    def test_legacy_text_call_and_ranker_signature(self):
        # 模拟仍只有旧参数签名的调用方排序器，验证不强行传递新关键字。
        delegate = self.ranker

        class LegacyRanker:
            def rank(self, disease_query, observation_text, top_k=5, max_hops=2):
                return delegate.rank(disease_query=disease_query, observation_text=observation_text,
                                     top_k=top_k, max_hops=max_hops)

        pipeline = KGRAGPipeline(ranker=LegacyRanker(), client=self.client)
        observation = "患者面部出现珍珠样结节，伴出血。"
        result = pipeline.run("LEGACY", "基底细胞癌", observation, 5, 2)
        self.assertNotIn("structured_fields", self.ranker.received)
        self.assertEqual(self.patient_section(self.client.prompt), observation)
        self.assertEqual(result.user_observation, observation)
        self.assertTrue(any(a.entity_id == "SYM_001" for a in self.ranker.result[0]))

    def test_raw_partial_mappings_and_label_exclusion(self):
        raw = {"hurt": True, "grew": True, "diagnostic": "诊断标签不得泄漏"}
        result = self.pipeline.run("PARTIAL", "黑色素瘤", "旧文本称触痛及直径增大",
                                   top_k=100, structured_fields=raw)
        self.assertIn("患者存在疼痛。", result.user_observation)
        self.assertIn("患者存在皮损增长。", result.user_observation)
        self.assertNotIn("触痛", result.user_observation)
        self.assertNotIn("直径增大", result.user_observation)
        self.assertNotIn("诊断标签不得泄漏", self.client.prompt)
        self.assertFalse(any(p.role_profile.claim_usage == "PATIENT_SUPPORT" for p in self.ranker.result[1]))

    def test_empty_structured_snapshot_is_not_text_fallback(self):
        result = self.pipeline.run("EMPTY", "基底细胞癌", "", structured_fields={})
        self.assertIn("未提供出血信息", result.user_observation)
        self.assertEqual(self.ranker.result[0], [])
        with self.assertRaises(ValueError):
            self.pipeline.run("EMPTY_TEXT", "基底细胞癌", "")

    def test_pad_inputs_delete_before_rendering_and_preserve_mother_case(self):
        original = build_pad_input("PAD_BCC_001")
        removed = build_pad_input("PAD_BCC_001", ["bleed", "region"])
        self.assertEqual(original["structured_fields"]["bleed"], "True")
        self.assertIn("患者存在出血。", original["user_observation"])
        self.assertNotIn("bleed", removed["structured_fields"])
        self.assertNotIn("region", removed["structured_fields"])
        self.assertIn("未提供出血信息。", removed["user_observation"])
        self.assertNotIn("FACE", removed["user_observation"])
        self.assertNotIn("诊断", removed["user_observation"])
        self.assertEqual(build_pad_input("PAD_BCC_001"), original)
        with self.assertRaises(ValueError):
            build_pad_input("PAD_BCC_001", ["bleeed"])
        with self.assertRaises(ValueError):
            build_pad_input("UNKNOWN_CASE")

    def test_pad_rq1_actual_entry_with_mock_client(self):
        self.check_pad_entry(run_pad_rq1_pilot)

    def test_pad_rq2_actual_entry_with_mock_client(self):
        self.check_pad_entry(run_pad_rq2_pilot)

    def check_pad_entry(self, module):
        clients = []

        def offline_pipeline(**kwargs):
            client = MockLLMClient()
            clients.append(client)
            return KGRAGPipeline(client=client, **kwargs)

        # 运行实际入口的输入准备和调用逻辑；模型为模拟客户端，结果只写临时目录。
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "mock_results.json"
            with patch.object(module, "KGRAGPipeline", side_effect=offline_pipeline), \
                    patch.object(module, "OUTPUT_PATH", output), \
                    contextlib.redirect_stdout(io.StringIO()):
                module.main()
            results = json.loads(output.read_text())
        self.assertEqual(len(results), len(module.CONDITIONS))
        for condition, result in zip(module.CONDITIONS, results):
            with self.subTest(condition=condition["condition_id"]):
                expected = build_pad_input(condition["condition_id"].rsplit("_", 1)[0],
                                           condition.get("removed_evidence", []))
                self.assertEqual(result["structured_fields"], expected["structured_fields"])
                self.assertEqual(result["user_observation"], expected["user_observation"])
                self.assertEqual(result["user_observation"], format_pad_observation(result["structured_fields"]))
                self.assertEqual(result["model_name"], "mock")
                self.assertEqual(result["run_status"], "success")
        self.assertTrue(clients)


if __name__ == "__main__":
    unittest.main(verbosity=2)
