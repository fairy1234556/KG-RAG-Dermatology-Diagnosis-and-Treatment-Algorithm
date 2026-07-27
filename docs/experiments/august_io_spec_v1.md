# 2026 年 8 月实验输入输出规范 V1.0

## 1. 适用范围

本规范适用于以下三种实验方法：

- 纯 LLM
- 普通 RAG
- KG-RAG

三种方法必须使用同一批测试样例，并输出统一结构。

## 2. 输入文件

输入文件：

`experiments/data/august_test_cases.csv`

## 3. 输入字段

- case_id：样例唯一编号
- true_label：HAM10000 标准标签
- candidate_disease：候选疾病
- observation_text：自然语言观察结果
- lesion_features：标准皮损特征
- anatomical_site：发病部位
- symptoms：伴随症状
- difficulty_level：样例难度
- case_type：样例类型
- source_type：样例来源
- notes：备注

## 4. 输出结构

统一使用 `rag/schemas.py` 中的 `KGRAGResult`。

输出必须包含：

- 候选疾病
- 观察匹配情况
- 支持证据
- 鉴别诊断
- 证据路径
- 风险提示
- 就医建议
- 证据不足说明
- 证据来源
- 模型名称
- Prompt 版本
- 响应时间
- 运行状态

## 5. 医学安全要求

- 不得将候选疾病表述为确诊
- 不得输出药物剂量或具体处方
- 不得生成证据之外的医学事实
- 证据不足时必须明确说明
- 输出仅用于辅助解释与健康信息参考

## 6. 版本管理

当前输入输出规范版本：V1.0

当前 KG-RAG Prompt 版本：kg_rag_v1.0