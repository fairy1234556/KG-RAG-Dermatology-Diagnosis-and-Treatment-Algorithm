# 图谱路径检索与证据排序规范 V1.0

## 1. 文档目的

本文档说明皮肤病知识图谱辅助诊断系统中图谱路径检索与证据排序模块的设计方案、输入输出、评分方法、验证样例及适用边界。

该模块位于语义锚点识别之后，负责根据候选疾病和用户观察结果，从知识图谱中检索相关证据路径，并按照可解释评分规则返回 Top-k 证据链。

本模块输出仅用于候选疾病的知识证据组织和辅助解释，不直接构成临床诊断结论。

---

## 2. 模块位置

任务三包含以下文件：

- `configs/relation_weights.yaml`
- `kg/path_retriever.py`
- `kg/path_ranker.py`
- `experiments/validate_path_ranking.py`
- `docs/experiments/path_ranking_spec_v1.md`

依赖模块：

- `rag/semantic_anchor.py`
- `kg/csv/entity_nodes.csv`
- `kg/csv/triples.csv`
- `kg/csv/entity_aliases.csv`

---

## 3. 输入定义

### 3.1 候选疾病

候选疾病支持以下输入形式：

- 中文标准名称；
- 英文标准名称；
- HAM10000 疾病标签；
- 疾病实体编号；
- 复合疾病名称中的独立名称。

示例：

```text
基底细胞癌
Basal Cell Carcinoma
bcc
DIS_003
光化性角化病
表皮内癌
光化性角化病/表皮内癌