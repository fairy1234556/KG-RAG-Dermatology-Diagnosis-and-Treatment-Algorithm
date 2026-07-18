from pathlib import Path
import sys
from textwrap import dedent

# 让 rag/ 目录下的脚本可以导入 kg/ 目录中的模块
PROJECT_ROOT = Path(__file__).resolve().parents[1]
KG_DIR = PROJECT_ROOT / "kg"
sys.path.append(str(KG_DIR))

from kg_evidence_context_demo import build_context_by_disease


def build_kg_rag_prompt(candidate_disease: str, user_observation: str) -> str:
    """Build a KG-RAG prompt from user observation and KG evidence context."""

    evidence_context = build_context_by_disease(candidate_disease)

    prompt = f"""
一、任务说明
你是一名医学知识图谱辅助解释助手。请结合用户观察结果与下方知识图谱证据，对候选疾病进行谨慎、可追溯的解释。你的回答仅用于健康信息参考，不构成医学诊断。

二、用户输入/观察结果
- 候选疾病：{candidate_disease}
- 用户观察：{user_observation}

三、知识图谱证据上下文
{evidence_context}

四、生成要求
1. 只能基于给定的知识图谱证据生成解释，不得使用证据上下文之外的信息补充结论。
2. 不允许编造未在证据中出现的医学结论；证据不足时必须明确说明“给定证据不足”。
3. 不得给出处方、药物剂量或具体用药方案。
4. 不得替代医生诊断，不得将候选疾病表述为已经确诊。
5. 输出内容必须体现“用户观察结果”与“知识图谱证据”之间的对应关系。
6. 每条支持证据必须尽量对应到知识图谱中的证据路径、evidence_text 或 source。
7. 如果某一项内容在知识图谱证据中没有直接依据，必须标注为“给定证据不足”。
8. 回答应保持谨慎，使用“可能支持”“提示需要考虑”“建议进一步评估”等表述，避免绝对化诊断。

五、输出格式约束
请严格按照以下固定格式输出，不要增加或删除一级栏目：

候选疾病：
- 中文名称：
- 英文名称：
- 疾病 ID：
- 结论表述：

用户观察与证据匹配：
- 观察 1：
  - 匹配情况：
  - 对应证据路径：
  - evidence_text：
  - source：
- 观察 2：
  - 匹配情况：
  - 对应证据路径：
  - evidence_text：
  - source：
- 观察 3：
  - 匹配情况：
  - 对应证据路径：
  - evidence_text：
  - source：

支持证据：
1.
   - 证据路径：
   - evidence_text：
   - source：
2.
   - 证据路径：
   - evidence_text：
   - source：

鉴别诊断：
- 需要鉴别的疾病或病变：
- 对应证据路径：
- evidence_text：
- source：

风险提示：
- 风险说明：
- 对应证据路径：
- evidence_text：
- source：

就医建议：
- 建议内容：
- 对应证据路径：
- evidence_text：
- source：

证据不足说明：
- 给定证据不足的内容：
- 原因说明：
"""
    return dedent(prompt).strip()


def main() -> None:
    candidate_disease = "血管性皮损"
    user_observation = "患者皮损表现为红色或紫红色血管样皮损。"

    prompt = build_kg_rag_prompt(
        candidate_disease=candidate_disease,
        user_observation=user_observation,
    )

    print(prompt)


if __name__ == "__main__":
    main()
    
