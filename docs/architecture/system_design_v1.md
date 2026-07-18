# 基于知识图谱增强的皮肤病智能辅助诊疗系统 V1.0 总体设计

## 1. 设计目标

本系统在当前“基于知识图谱增强与证据一致性校验的皮肤病辅助诊断”研究仓库基础上扩展，不创建独立新仓库。V1.0 以皮肤科医生为核心用户，以普通患者为补充用户，疾病范围限定为 HAM10000 七类皮肤病变：黑色素瘤、黑色素细胞痣、基底细胞癌、光化性角化病/表皮内癌、良性角化样病变、皮肤纤维瘤、血管性皮损。

系统目标是把现有知识图谱、KG-RAG Prompt 和初步评价成果封装为可复用后端能力，并在其上建设病例录入、候选疾病排序、证据路径展示、KG-RAG 辅助解释、证据一致性校验、医生审核和报告保存闭环。

重要边界：

- 系统结果为候选疾病和辅助解释，不替代医生最终诊断。
- 规则评分只用于候选排序，不称为患病概率。
- V1.0 图片仅用于上传、预览和病例关联，不伪造自动图像分类能力。
- 不输出处方、药物剂量或替代医生的治疗决定。
- 患者端仅提供通俗解释、关注/就医建议和引导。
- 研究人员角色 `researcher` 仅访问实验、评价、版本和脱敏研究材料，不访问未经授权的患者病例。
- 保留原始实验代码、CSV 和输出记录，作为论文实验和系统复现基线。

## 2. 当前仓库审查

### 2.1 当前仓库结构

当前仓库已经形成研究原型闭环，主要目录如下：

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
├── rag/
│   ├── kg_rag_prompt_demo.py
│   └── kg_rag_prompt_demo_v2.py
├── work/
│   ├── test_cases.csv
│   └── evaluation_results.csv
├── outputs/
└── experiments/
```

### 2.2 已实现能力

当前代码和数据已经实现以下能力：

1. 知识图谱 CSV 数据基线
   - `kg/csv/entity_nodes.csv` 存储疾病、皮损表现、部位、症状、检查、鉴别诊断、风险提示、就医建议等实体。
   - `kg/csv/triples.csv` 存储疾病与实体之间的关系路径、证据文本和来源标记。
   - `kg/csv/source_references.csv` 存储来源记录及其关联三元组。

2. 图谱查询能力
   - `kg/kg_query_demo.py` 提供 `KnowledgeGraphQuery`。
   - 支持按疾病查询三元组。
   - 支持按关系类型查询疾病相关证据。
   - 支持按皮损特征反向查询相关疾病。
   - 支持把来源信息附加到三元组查询结果。

3. 证据上下文构造能力
   - `kg/kg_evidence_context_demo.py` 提供 `EvidenceContextBuilder`。
   - 能按候选疾病组织结构化证据上下文。
   - 按主要皮损表现、常见部位、伴随症状、建议检查、鉴别诊断、风险提示、就医建议、证据来源分节。

4. KG-RAG Prompt 构造能力
   - `rag/kg_rag_prompt_demo.py` 提供 `KGRAGPromptBuilder`。
   - 能把候选疾病、用户观察和图谱证据上下文组合为医学安全约束 Prompt。
   - Prompt 已包含不替代医生诊断、不编造证据、不输出处方剂量等边界。

5. KG-RAG Prompt V2 样例
   - `rag/kg_rag_prompt_demo_v2.py` 提供更细的输出格式。
   - 强调用户观察与证据路径、证据文本、来源之间的对应关系。

6. 实验样例与评价记录
   - `work/test_cases.csv` 记录七类疾病代表性测试样例。
   - `work/evaluation_results.csv` 记录证据命中、无依据生成、路径一致性、证据覆盖等评价结果。
   - `outputs/` 保存样例输出。
   - `experiments/logs/` 保存实验运行记录。

### 2.3 可直接复用代码

可直接复用的模块包括：

| 文件 | 可复用内容 | 建议封装方式 |
|---|---|---|
| `kg/kg_query_demo.py` | CSV 读取、实体检索、疾病证据查询、关系过滤、特征反查 | 封装为 `backend/app/services/kg_repository.py` 或 `kg_service.py` |
| `kg/kg_evidence_context_demo.py` | 按疾病构造结构化证据上下文 | 封装为 `EvidenceContextService` |
| `rag/kg_rag_prompt_demo.py` | 安全约束 Prompt 构造 | 拆出 Prompt 模板，封装为 `PromptBuilderService` |
| `rag/kg_rag_prompt_demo_v2.py` | 更细粒度观察-证据匹配输出格式 | 迁移为 V1.0 默认 Prompt 模板候选 |
| `work/test_cases.csv` | 七类疾病演示用例 | 作为实验模块和接口测试样例 |
| `work/evaluation_results.csv` | 初步人工评价指标 | 作为实验结果导入或展示基线 |

复用原则：

- 保留原文件不动，先在后端服务层建立适配器。
- Demo 代码中的纯函数和类可以被导入，但不应让 Web 接口直接依赖脚本式 `main()`。
- 后续可以逐步把稳定逻辑迁移到 `backend/app/services/`，原 Demo 留作研究记录。

### 2.4 发现的问题

#### 2.4.1 路径问题

- `kg/kg_query_demo.py` 默认从自身目录下的 `csv` 读取数据，适合作为脚本运行，但服务化后需要支持配置化数据目录。
- `rag/kg_rag_prompt_demo.py` 手动修改 `sys.path`，虽然能解决直接运行问题，但不适合作为长期后端导入方式。
- `rag/kg_rag_prompt_demo_v2.py` 通过把 `kg` 目录追加到 `sys.path` 后直接导入 `kg_evidence_context_demo`，与包结构耦合较强。

建议：

- 在后端中统一从配置项读取 `KG_CSV_DIR`。
- 为 `kg` 和 `rag` 增加稳定包导入策略时，应避免破坏原 Demo。
- 新后端服务应通过适配器调用现有类，而不是继续复制 `sys.path` 逻辑。

#### 2.4.2 导入方式问题

- `kg/kg_evidence_context_demo.py` 使用 `from kg_query_demo import KnowledgeGraphQuery`，依赖运行位置。
- `rag/kg_rag_prompt_demo.py` 与 `rag/kg_rag_prompt_demo_v2.py` 的导入风格不一致。

建议：

- 后端服务层统一导入路径。
- 后续可考虑新增 `kg/__init__.py` 和 `rag/__init__.py`，但本轮不修改。
- 保留 Demo 脚本的直接运行能力，并在新服务中提供稳定导入包装。

#### 2.4.3 代码耦合问题

- CSV 读取、实体匹配、证据组织和终端格式化在同一类或同一文件中混合。
- Prompt 文本硬编码在 Python 文件中，不便于后台版本管理和 Prompt 迭代。
- 证据上下文以 Markdown 字符串为主，缺少结构化 JSON 输出，前端难以直接展示每条证据的字段。

建议：

- 后端服务层把图谱查询结果转换为结构化对象。
- Prompt 模板迁移到 `prompts/` 目录，数据库仅记录版本、名称、状态和模板文件路径。
- 查询服务同时提供结构化 JSON 和 Markdown 上下文两种输出。

#### 2.4.4 数据字段问题

- `source_references.csv` 存在一个空表头字段，后续导入或校验时需要清洗。
- `source_references.csv` 当前主要通过 `used_for_triples` 反向关联三元组，缺少更规范的 `reference_id` 到 `triple_id` 多对多表。
- `triples.csv` 已包含 `source` 和 `evidence_text`，同时 `source_references.csv` 也有来源信息，存在一定冗余。
- 当前 CSV 能支撑图谱证据查询，但不能直接支撑病例、医生审核、报告版本、操作日志等业务数据。

建议：

- V1.0 保留 CSV 作为图谱基线，不直接迁移或覆盖。
- 后端加载 CSV 时做字段规范化和空字段容错。
- SQLite 只保存业务数据、版本引用、报告和审核记录。

#### 2.4.5 运行方式问题

- 当前 Demo 主要通过命令行运行，缺少统一入口。
- 没有接口层、权限层、病例状态流转和持久化业务模型。
- 实验评价仍以人工记录为主，未形成自动化任务和结果表。

建议：

- 第一阶段先封装 FastAPI 服务，不改变研究代码。
- 用服务层暴露疾病查询、特征反查、证据上下文、Prompt 构造等能力。
- 实验模块先读取现有 `work` 和 `outputs`，后续再加入自动任务表。

### 2.5 CSV 字段对系统开发的支持情况

| CSV | 当前字段 | 支持能力 | 不足 |
|---|---|---|---|
| `entity_nodes.csv` | `id`, `entity_type`, `name_cn`, `name_en`, `alias`, `source`, `note` | 支持实体检索、同义词匹配、疾病范围控制 | 缺少实体状态、版本、生效时间、创建人 |
| `triples.csv` | `triple_id`, `head_id`, `head_cn`, `head_type`, `relation_cn`, `relation_en`, `tail_id`, `tail_cn`, `tail_type`, `source`, `evidence_text`, `note` | 支持证据路径、关系筛选、候选解释 | 缺少关系权重、证据强度、审核状态、版本字段 |
| `source_references.csv` | `source_id`, `source_name`, `source_type`, `used_for_triples`, 空字段 | 支持来源追溯 | 空字段需容错；缺少 URL、发布日期、访问日期、引用格式 |
| `work/test_cases.csv` | `case_id`, `candidate_disease`, `disease_id`, `ham10000_label`, `user_observation`, `expected_key_evidence`, `output_file`, `status` | 支持七类样例演示和测试 | 不适合承载真实病例 |
| `work/evaluation_results.csv` | `case_id`, `candidate_disease`, `ham10000_label`, `output_file`, `evidence_hit_rate`, `unsupported_claim_rate`, `path_consistency`, `evidence_coverage`, `overall_result`, `notes` | 支持初步实验评价展示 | 指标是定性记录，缺少任务、模型、Prompt、算法版本外键 |

结论：

- 现有 CSV 足以支持 V1.0 的图谱查询、证据展示、Prompt 构造和实验基线。
- 现有 CSV 不适合承载系统业务数据。
- 病例、审核、报告、模型调用、版本追踪、操作日志应进入 SQLite。

## 3. 项目迁移与目录规划

### 3.1 迁移原则

1. 在当前仓库内扩展，不创建独立新仓库。
2. 保留 `kg`、`rag`、`work`、`outputs`、`experiments`。
3. 原始 CSV、实验输出和核心研究代码不删除、不覆盖。
4. 新增后端、前端、文档、数据、Prompt 和测试目录。
5. 服务化优先通过适配器复用 Demo，避免一次性重构研究代码。

### 3.2 建议目标目录

```text
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── main.py
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── router/
│   │   └── stores/
│   └── tests/
├── docs/
│   ├── architecture/
│   ├── database/
│   ├── pages/
│   ├── api/
│   └── plans/
├── data/
│   ├── sqlite/
│   ├── uploads/
│   ├── exports/
│   └── snapshots/
├── prompts/
│   ├── kg_rag/
│   ├── patient/
│   └── validation/
├── tests/
│   ├── fixtures/
│   ├── integration/
│   └── regression/
├── kg/
├── rag/
├── work/
├── outputs/
└── experiments/
```

### 3.3 目录职责

| 目录 | 职责 |
|---|---|
| `backend/` | FastAPI 后端、SQLAlchemy 模型、服务层、接口层 |
| `frontend/` | Vue 3 + TypeScript + Element Plus 前端 |
| `docs/` | 架构、数据库、页面、接口、计划文档 |
| `data/sqlite/` | 本地 SQLite 数据库文件，开发环境使用 |
| `data/uploads/` | 皮损图片上传文件，仅作病例资料 |
| `data/exports/` | 报告导出文件 |
| `data/snapshots/` | 图谱 CSV 快照、Prompt 快照、实验快照 |
| `prompts/` | KG-RAG、患者端解释、证据校验 Prompt 模板 |
| `tests/` | 跨后端、前端和研究算法的回归测试 |

## 4. Demo 代码后端封装方案

### 4.1 服务分层

建议后端采用如下分层：

```text
API Router
  -> Schema/Pydantic
    -> Service
      -> Repository/Adapter
        -> Existing KG/RAG demo code or SQLite
```

### 4.2 图谱服务

封装目标：

- 加载 `kg/csv/*.csv`。
- 提供疾病查询、关系查询、特征反查、实体搜索。
- 输出结构化 JSON。
- 保留证据路径、证据文本、来源标识。

建议服务：

- `KnowledgeGraphRepository`
- `KnowledgeGraphService`
- `EvidencePathService`

对现有代码的映射：

- `KnowledgeGraphQuery.query_by_disease` -> `GET /api/kg/diseases/{disease_id}/evidence`
- `KnowledgeGraphQuery.query_by_relation` -> `GET /api/kg/diseases/{disease_id}/relations/{relation}`
- `KnowledgeGraphQuery.query_by_feature` -> `GET /api/kg/features/{feature_id}/diseases`

### 4.3 证据上下文服务

封装目标：

- 把候选疾病相关证据整理为 LLM 可用上下文。
- 同时返回 Markdown 和结构化 sections。

建议服务：

- `EvidenceContextService`

对现有代码的映射：

- `EvidenceContextBuilder.build_context_by_disease` -> `POST /api/kg-rag/evidence-context`

### 4.4 Prompt 服务

封装目标：

- 根据病例摘要、候选疾病和证据上下文构造 Prompt。
- 支持 Prompt 版本管理。
- 支持模板降级模式。

建议服务：

- `PromptTemplateService`
- `KGRAGPromptService`

对现有代码的映射：

- `KGRAGPromptBuilder.build_prompt` -> `POST /api/kg-rag/prompts`
- `build_kg_rag_prompt` V2 -> V1.0 默认专业解释模板候选

### 4.5 候选疾病排序服务

当前仓库尚未形成完整自动排序服务，但已有特征反查基础。V1.0 可在后端新增规则化评分服务：

```text
Score(d) = alpha * Mf + beta * Ml + gamma * Ms + eta * Ce - lambda * Cf
```

其中：

- `Mf`：皮损特征匹配分。
- `Ml`：发病部位匹配分。
- `Ms`：伴随症状匹配分。
- `Ce`：有效证据覆盖分。
- `Cf`：明确冲突特征惩罚。

评分约束：

- 风险提示是疾病风险说明，不是患者诊断匹配特征，不参与候选疾病排序。
- 未填写、未知、未观察不能作为冲突惩罚。
- 只有用户明确描述且与图谱证据矛盾时，才计入 `Cf`。
- 候选疾病形成后，再单独生成风险提示和就医建议。
- 输出必须展示分项，所有评分均不得称为患病概率。

### 4.6 证据一致性校验服务

当前仓库有评价指标记录，但未实现自动校验服务。V1.0 建议分步实现：

1. 基于规则和模板拆分生成内容中的医学声明。
2. 将声明映射到候选疾病、关系和实体。
3. 与图谱三元组匹配。
4. 标记 `supported`、`partially_supported`、`unsupported`、`not_verifiable`。
5. 计算 Observation Evidence Hit Rate、Unsupported Claim Rate、Path Consistency Score、Evidence Coverage Rate。

指标定义固定为：

- `OEHR`：Observation Evidence Hit Rate，命中图谱证据的有效观察锚点数 / 可标准化的有效观察锚点总数。
- `UCR`：Unsupported Claim Rate，unsupported 声明数 / 可验证医学声明总数。`not_verifiable` 不得自动算作 `supported`，需要单独记录。
- `PCS`：Path Consistency Score，疾病、关系和尾实体均与图谱路径一致的声明数 / 成功映射为结构化路径的声明总数。
- `ECR`：Evidence Coverage Rate，输出实际使用的相关证据类型数 / 当前任务可用的相关证据类型数。

### 4.7 模型适配与降级

模型服务应采用可替换适配层：

- `TemplateGenerationAdapter`：不依赖外部模型，保证演示可运行。
- `OpenAICompatibleAdapter`：后续接入大模型。

当模型不可用时，系统应记录降级原因，并用模板模式生成结构化辅助解释。

## 5. 总体架构

### 5.1 逻辑架构

```text
Frontend
  - Doctor Portal
  - Patient Portal
  - Knowledge Admin
  - Research Portal
  - System and Experiment Admin

Backend API
  - Auth API
  - Case API
  - Image API
  - KG API
  - Analysis API
  - KG-RAG API
  - Evidence Validation API
  - Review API
  - Report API
  - Experiment API

Service Layer
  - Case Service
  - Semantic Anchor Service
  - Candidate Ranking Service
  - KG Query Service
  - Evidence Context Service
  - Prompt Service
  - Generation Service
  - Claim Validation Service
  - Report Service
  - Audit Log Service

Data Layer
  - SQLite: business data, cases, reports, reviews, versions, logs
  - CSV: KG baseline, test cases, evaluation baseline
  - File Storage: uploaded images and report exports
```

### 5.2 数据流

医生端主流程：

1. 医生创建匿名病例。
2. 录入临床观察和可选图片。
3. 系统识别语义锚点并标准化到图谱实体。
4. 系统通过完整分析编排完成候选排序、证据召回、KG-RAG 或模板生成、声明校验和报告草稿。
5. 医生查看候选疾病、证据路径、风险提示、辅助解释和校验结果。
6. 医生审核候选疾病、解释和报告。
7. 系统保存报告、医生意见、版本和日志。

患者端主流程：

1. 患者确认免责声明。
2. 填写基础观察和可选图片。
3. 系统进行范围判断和语义标准化。
4. 系统返回通俗解释、关注/就医建议和引导。
5. 患者端风险表达使用“需常规关注”“建议预约皮肤科评估”“建议尽快就医评估”，不使用容易被理解为患病概率的低/中/高风险。
6. 不显示最终诊断、处方、剂量、医生端完整候选评分或专业实验指标。

## 6. V1.0 技术选型

| 层级 | 建议技术 | 说明 |
|---|---|---|
| 后端 | Python, FastAPI, Pydantic | 保持与现有研究代码一致 |
| ORM | SQLAlchemy | 支持 SQLite，后续可迁移 PostgreSQL |
| 数据库 | SQLite | V1.0 业务数据与演示部署足够 |
| 图谱数据 | CSV | 保留论文实验基线 |
| 前端 | Vue 3, TypeScript, Vite, Element Plus | 医生端优先，患者端移动适配 |
| 图谱可视化 | ECharts Graph | 支持疾病子图和证据详情联动 |
| 测试 | pytest, 前端基础测试 | 优先覆盖评分、检索、校验、权限 |

## 7. 当前阶段不做事项

- 不创建实际前后端项目。
- 不创建数据库。
- 不安装依赖。
- 不修改现有 CSV。
- 不覆盖 `outputs` 和 `experiments`。
- 不实现图片自动分类。
- 不接入 Neo4j。
- 不把演示系统表述为已达到临床应用水平。
