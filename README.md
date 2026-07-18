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
```

## 4. V1.0 前后端演示

第二阶段新增 `frontend/`，用于展示中文角色入口、医生工作台、患者健康咨询、知识图谱查询和 KG-RAG 辅助解释页面。

后端启动：

```bash
uvicorn backend.app.main:app --reload
```

前端启动：

```bash
cd frontend
npm install
npm run dev
```

前端业务请求统一使用 `/api`，由 Vite 开发代理转发至 `http://127.0.0.1:8000`。当前为演示模式，真实病例保存、医生审核、真实大模型调用、图像分类和 Grad-CAM 暂未接入。
