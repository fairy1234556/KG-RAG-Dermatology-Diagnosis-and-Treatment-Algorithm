# 基于知识图谱增强与证据一致性校验的皮肤病辅助诊断方法研究与实现

## 1. 项目简介

本项目围绕皮肤病辅助诊断场景，构建面向 HAM10000 数据集七类皮肤病的医学知识图谱，并在此基础上实现知识图谱增强生成流程。项目目标不是替代医生诊断，而是通过知识图谱证据为候选疾病生成谨慎、可追溯、可解释的辅助说明。

当前系统主要完成以下功能：

1. 构建皮肤病领域知识图谱，包括疾病、皮损表现、常见部位、伴随症状、检查方式、鉴别诊断、风险提示、就医建议和证据来源等信息。
2. 基于疾病名称查询知识图谱证据。
3. 将知识图谱中的三元组证据组织为大模型可读取的证据上下文。
4. 构建 KG-RAG Prompt，使生成结果能够围绕候选疾病、用户观察和图谱证据进行解释。
5. 针对 HAM10000 七类疾病构造代表性测试样例，生成结构化辅助解释结果。
6. 对输出结果进行初步人工评价，记录证据命中、无依据生成、路径一致性和证据覆盖情况。

## 2. 数据集与疾病范围

本项目当前以 HAM10000 数据集为主要研究对象，疾病范围限定为 HAM10000 中的七类皮肤病标签：

| HAM10000 标签 | 中文名称 | 英文名称 |
|---|---|---|
| mel | 黑色素瘤 | Melanoma |
| nv | 黑色素细胞痣 | Melanocytic Nevus |
| bcc | 基底细胞癌 | Basal Cell Carcinoma |
| akiec | 光化性角化病/表皮内癌 | Actinic Keratosis / Intraepithelial Carcinoma |
| bkl | 良性角化样病变 | Benign Keratosis-like Lesion |
| df | 皮肤纤维瘤 | Dermatofibroma |
| vasc | 血管性皮损 | Vascular Lesion |

当前阶段不继续扩展疾病类型，重点放在 KG-RAG 流程实现、证据一致性控制和实验样例验证。

## 3. 项目目录结构

```text
.
├── kg/
│   ├── csv/
│   │   ├── entity_nodes.csv
│   │   ├── triples.csv
│   │   └── source_references.csv
│   ├── kg_query_demo.py
│   ├── kg_evidence_context_demo.py
│   └── README.md
│
├── rag/
│   ├── kg_rag_prompt_demo.py
│   └── kg_rag_prompt_demo_v2.py
│
├── outputs/
│   ├── kg_rag_case_001_bcc.md
│   ├── kg_rag_case_002_melanoma.md
│   ├── kg_rag_case_003_nevus.md
│   ├── kg_rag_case_004_akiec.md
│   ├── kg_rag_case_005_bkl.md
│   ├── kg_rag_case_006_df.md
│   ├── kg_rag_case_007_vasc.md
│   └── evaluation_summary.md
│
├── experiments/
│   └── logs/
│       ├── kg_rag_prompt_case_001_bcc.txt
│       ├── kg_rag_prompt_case_002_melanoma.txt
│       ├── kg_rag_prompt_case_003_nevus.txt
│       ├── kg_rag_prompt_case_004_akiec.txt
│       ├── kg_rag_prompt_case_005_bkl.txt
│       ├── kg_rag_prompt_case_006_df.txt
│       └── kg_rag_prompt_case_007_vasc.txt
│
├── work/
│   ├── test_cases.csv
│   └── evaluation_results.csv
│
└── README.md
4. 知识图谱构建说明

当前知识图谱围绕 HAM10000 七类疾病构建，主要包括以下信息：

疾病实体
皮损表现实体
常见部位实体
伴随症状实体
检查方式实体
鉴别诊断实体
风险提示实体
就医建议实体
证据来源信息

知识图谱采用 CSV 文件进行存储，核心文件包括：

kg/csv/entity_nodes.csv
kg/csv/triples.csv
kg/csv/source_references.csv

其中：

entity_nodes.csv 用于存储实体节点。
triples.csv 用于存储疾病与症状、部位、检查方式、鉴别诊断等之间的三元组关系。
source_references.csv 用于存储证据来源，包括医学网站、指南或论文来源。

当前知识图谱 V1 版本已完成 70 个实体节点、102 条三元组和 25 条证据来源记录。

5. 已实现功能
5.1 知识图谱查询

运行以下命令可以测试知识图谱查询功能：

python3 kg/kg_query_demo.py

该脚本支持以下查询：

按疾病查询相关三元组。
按关系类型查询疾病证据。
按皮损特征反向查询可能相关疾病。
5.2 证据上下文生成

运行以下命令可以将知识图谱证据组织为大模型可读取的上下文：

python3 kg/kg_evidence_context_demo.py

输出内容包括：

候选疾病
主要皮损表现
常见部位
伴随症状
建议检查
鉴别诊断
风险提示
就医建议
证据来源
5.3 KG-RAG Prompt 构造

运行以下命令可以生成 KG-RAG Prompt：

python3 rag/kg_rag_prompt_demo_v2.py

该脚本会根据候选疾病和用户观察结果，自动读取知识图谱证据，并生成结构化 Prompt。Prompt 中包含任务说明、用户观察、知识图谱证据上下文、生成要求和输出格式约束。

5.4 代表性样例输出

当前已完成 HAM10000 七类疾病的代表性 KG-RAG 输出样例，结果保存在：

outputs/

包括：

kg_rag_case_001_bcc.md
kg_rag_case_002_melanoma.md
kg_rag_case_003_nevus.md
kg_rag_case_004_akiec.md
kg_rag_case_005_bkl.md
kg_rag_case_006_df.md
kg_rag_case_007_vasc.md

每个样例均包含：

输入信息
候选疾病
用户观察与证据匹配
支持证据
鉴别诊断
风险提示
就医建议
证据不足说明
6. 初步评价设计

当前实验采用人工核查方式进行初步评价，评价结果记录在：

work/evaluation_results.csv

评价指标包括：

Evidence Hit Rate：证据命中情况。
Unsupported Claim Rate：无依据生成情况。
Path Consistency Score：路径一致性。
Evidence Coverage Rate：证据覆盖情况。

由于当前阶段尚未接入自动化批量推理和自动评分模块，因此评价结果采用 high、medium、low、consistent、pass 等定性记录方式。

实验总结说明保存在：

outputs/evaluation_summary.md
7. 当前阶段成果

截至当前阶段，本项目已经完成以下内容：

明确 HAM10000 七类疾病作为研究范围。
完成皮肤病知识图谱 V1 构建。
完成知识图谱 CSV 文件整理。
完成知识图谱查询脚本。
完成知识图谱证据上下文生成脚本。
完成 KG-RAG Prompt V2 模板。
完成七类疾病代表性 KG-RAG 输出样例。
完成初步实验评价表。
完成实验结果说明文档。

当前项目已经形成从“知识图谱构建—证据检索—Prompt 构造—KG-RAG 输出—人工评价记录”的完整小闭环。

8. 后续工作方向

后续工作主要包括：

优化 KG-RAG Prompt，使输出更加稳定、简洁和医学安全。
扩展测试样例数量，每类疾病增加多个不同观察样例。
接入真实大模型 API，完成批量生成实验。
设计自动化评价脚本，对证据命中、路径一致性和无依据生成情况进行半自动统计。
将系统方法、实验设计和结果分析整理进论文正文。
根据论文需要补充系统架构图、流程图和实验结果表格。
9. 运行环境说明

本项目当前主要使用 Python 运行，建议在项目根目录下执行脚本。

示例命令：

python3 kg/kg_query_demo.py
python3 kg/kg_evidence_context_demo.py
python3 rag/kg_rag_prompt_demo_v2.py

运行脚本前应确保当前终端路径位于项目根目录。

保存后，在终端运行：

```bash
cat README.md

然后再运行：

ls

你应该能看到根目录下有：

README.md
kg
rag
outputs
experiments
work