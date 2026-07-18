# V1.0 数据库设计

## 1. 设计原则

V1.0 采用 SQLite + SQLAlchemy。SQLite 保存系统业务数据，现有 CSV 继续作为知识图谱和实验基线。数据库设计强调匿名化、可追溯、版本化和医生审核闭环。

核心原则：

- 病例、报告、医生审核、操作日志进入 SQLite。
- 原始图谱 CSV 不直接覆盖，不在 V1.0 中强制迁移为数据库图谱。
- SQLite 中只保存图谱版本引用、实体 ID、三元组 ID 和快照元数据。
- 图片文件保存在文件系统，数据库保存元数据和关联关系。
- 删除病例采用归档或软删除，涉及审计的历史记录不可物理覆盖。
- 所有生成和分析结果必须记录图谱、Prompt、模型和算法版本。

## 2. 数据存储边界

### 2.1 继续保存在 CSV 的数据

| 数据 | 位置 | 原因 |
|---|---|---|
| 实体节点 | `kg/csv/entity_nodes.csv` | 论文实验基线，便于复现 |
| 图谱三元组 | `kg/csv/triples.csv` | 保持当前研究代码兼容 |
| 来源引用 | `kg/csv/source_references.csv` | 保持证据追溯基线 |
| 测试样例 | `work/test_cases.csv` | 用于实验和回归测试 |
| 初步评价结果 | `work/evaluation_results.csv` | 用于论文材料和实验展示 |
| 样例输出 | `outputs/` | 保留生成结果记录 |
| 实验日志 | `experiments/` | 保留实验运行记录 |

### 2.2 进入 SQLite 的数据

| 数据 | 原因 |
|---|---|
| 用户与角色 | 支持登录、权限、审计 |
| 匿名患者档案 | 支持病例归属和隐私控制 |
| 病例 | 支持医生端闭环 |
| 临床观察 | 支持结构化录入和语义标准化 |
| 皮损图片元数据 | 支持上传、预览和病例关联 |
| 语义锚点与标准化结果 | 支持输入追溯和医生修正 |
| 分析任务 | 支持状态流转、降级、版本复现 |
| 候选疾病及评分分项 | 支持 Top-3 展示和非概率解释 |
| 证据路径 | 支持每条主要证据追溯 |
| 生成报告 | 支持报告版本与导出 |
| 医学声明与校验结果 | 支持一致性校验和指标统计 |
| 医生审核与反馈 | 支持最终临床意见和修订历史 |
| 图谱、Prompt、模型、算法版本 | 支持复现 |
| 操作日志 | 支持安全审计 |

## 3. 表设计

字段类型以 SQLAlchemy 常用类型表达：`Integer`、`String`、`Text`、`Boolean`、`DateTime`、`Date`、`Float`、`JSON`。SQLite 中 `JSON` 可映射为文本 JSON。

### 3.1 `roles` 角色表

用途：定义系统角色。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `code` | String(50) | 否 | 否 | 是 | 唯一；如 `doctor`, `patient`, `knowledge_admin`, `researcher`, `system_admin` |
| `name` | String(100) | 否 | 否 | 是 | 角色中文名 |
| `description` | Text | 否 | 否 | 否 | 说明 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

角色边界：

- `researcher` 仅访问实验、评价、版本和脱敏研究材料。
- `researcher` 不访问未经授权的患者病例、医生审核详情或可识别个人信息。

### 3.2 `users` 用户表

用途：保存登录用户与身份状态。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `username` | String(80) | 否 | 否 | 是 | 唯一 |
| `password_hash` | String(255) | 否 | 否 | 是 | 不保存明文密码 |
| `display_name` | String(100) | 否 | 否 | 是 | 展示名，可为虚拟账号名 |
| `email` | String(255) | 否 | 否 | 否 | 唯一，可为空 |
| `is_active` | Boolean | 否 | 否 | 是 | 默认 true |
| `last_login_at` | DateTime | 否 | 否 | 否 | 最近登录 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |
| `updated_at` | DateTime | 否 | 否 | 是 | 更新时间 |

主要约束：

- `username` 唯一。
- `password_hash` 不可为空。
- 演示账号不得内置真实个人敏感信息。

### 3.3 `user_roles` 用户角色关联表

用途：支持一个用户拥有多个角色。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `user_id` | Integer | 是 | `users.id` | 是 | 联合主键 |
| `role_id` | Integer | 是 | `roles.id` | 是 | 联合主键 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.4 `anonymous_patients` 匿名患者档案表

用途：保存匿名患者档案，不保存真实姓名和身份证号。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `patient_code` | String(80) | 否 | 否 | 是 | 唯一匿名编号 |
| `owner_user_id` | Integer | 否 | `users.id` | 否 | 患者端账号归属，可为空 |
| `sex` | String(20) | 否 | 否 | 否 | `male`, `female`, `unknown`, `other` |
| `birth_year` | Integer | 否 | 否 | 否 | 可为空，避免保存完整生日 |
| `age_at_first_visit` | Integer | 否 | 否 | 否 | 演示病例可直接存年龄 |
| `notes` | Text | 否 | 否 | 否 | 脱敏备注 |
| `is_archived` | Boolean | 否 | 否 | 是 | 默认 false |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |
| `updated_at` | DateTime | 否 | 否 | 是 | 更新时间 |

### 3.5 `cases` 病例表

用途：保存医生端和患者端病例主记录。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `case_no` | String(80) | 否 | 否 | 是 | 唯一病例编号 |
| `patient_id` | Integer | 否 | `anonymous_patients.id` | 是 | 匿名患者 |
| `created_by_user_id` | Integer | 否 | `users.id` | 是 | 创建人 |
| `assigned_doctor_id` | Integer | 否 | `users.id` | 否 | 负责医生 |
| `source_channel` | String(30) | 否 | 否 | 是 | `doctor`, `patient`, `experiment` |
| `visit_date` | Date | 否 | 否 | 否 | 就诊日期 |
| `status` | String(30) | 否 | 否 | 是 | `draft`, `analyzing`, `pending_review`, `reviewed`, `archived` |
| `chief_complaint` | Text | 否 | 否 | 否 | 主诉或主要描述 |
| `initial_suspected_disease` | String(120) | 否 | 否 | 否 | 医生初步怀疑 |
| `scope_status` | String(30) | 否 | 否 | 是 | `in_scope`, `out_of_scope`, `insufficient` |
| `care_guidance_level` | String(40) | 否 | 否 | 否 | 患者端表达：`routine_attention`, `book_dermatology`, `seek_care_soon`, `unknown` |
| `is_archived` | Boolean | 否 | 否 | 是 | 默认 false |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |
| `updated_at` | DateTime | 否 | 否 | 是 | 更新时间 |

主要约束：

- `case_no` 唯一。
- 状态流转需由业务服务控制。
- 归档不删除审计数据。

### 3.6 `clinical_observations` 临床观察表

用途：保存病例观察信息，支持结构化和自由文本并存。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `body_site` | String(120) | 否 | 否 | 否 | 发病部位 |
| `duration_text` | String(120) | 否 | 否 | 否 | 病程原文 |
| `lesion_count` | String(80) | 否 | 否 | 否 | 数量，可为未知 |
| `diameter_mm` | Float | 否 | 否 | 否 | 直径 |
| `shape_features` | JSON | 否 | 否 | 否 | 形态多选 |
| `color_features` | JSON | 否 | 否 | 否 | 颜色多选 |
| `border_feature` | String(80) | 否 | 否 | 否 | 边界 |
| `symmetry_feature` | String(80) | 否 | 否 | 否 | 对称性 |
| `surface_features` | JSON | 否 | 否 | 否 | 鳞屑、破溃等 |
| `symptoms` | JSON | 否 | 否 | 否 | 瘙痒、疼痛等 |
| `bleeding` | String(30) | 否 | 否 | 否 | `yes`, `no`, `unknown` |
| `ulceration` | String(30) | 否 | 否 | 否 | `yes`, `no`, `unknown` |
| `change_description` | Text | 否 | 否 | 否 | 变化情况 |
| `history_text` | Text | 否 | 否 | 否 | 既往史、家族史、日晒、免疫等 |
| `free_text` | Text | 否 | 否 | 否 | 原始自由文本 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |
| `updated_at` | DateTime | 否 | 否 | 是 | 更新时间 |

主要约束：

- 字段允许未知或为空，不用默认值伪装临床事实。
- 原始文本必须保留。

### 3.7 `lesion_images` 皮损图片表

用途：保存图片元数据和病例关联。V1.0 不保存自动分类结果。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `uploaded_by_user_id` | Integer | 否 | `users.id` | 是 | 上传人 |
| `file_id` | String(120) | 否 | 否 | 是 | 唯一文件标识 |
| `original_filename` | String(255) | 否 | 否 | 是 | 原始文件名 |
| `stored_path` | String(500) | 否 | 否 | 是 | 本地存储路径 |
| `mime_type` | String(80) | 否 | 否 | 是 | 仅允许 JPG/JPEG/PNG |
| `file_size_bytes` | Integer | 否 | 否 | 是 | 文件大小 |
| `width` | Integer | 否 | 否 | 否 | 图片宽 |
| `height` | Integer | 否 | 否 | 否 | 图片高 |
| `description` | Text | 否 | 否 | 否 | 图片说明 |
| `is_deleted` | Boolean | 否 | 否 | 是 | 默认 false |
| `uploaded_at` | DateTime | 否 | 否 | 是 | 上传时间 |

### 3.8 `semantic_anchors` 语义锚点表

用途：保存从病例输入中识别出的疾病、特征、部位、症状等锚点。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `observation_id` | Integer | 否 | `clinical_observations.id` | 否 | 来源观察 |
| `raw_text` | String(255) | 否 | 否 | 是 | 原始短语 |
| `anchor_type` | String(50) | 否 | 否 | 是 | `disease`, `feature`, `site`, `symptom`, `risk`, `exam` |
| `normalized_entity_id` | String(80) | 否 | 否 | 否 | 对应 CSV 实体 ID |
| `normalized_name_cn` | String(120) | 否 | 否 | 否 | 标准中文名 |
| `normalized_name_en` | String(160) | 否 | 否 | 否 | 标准英文名 |
| `confidence_score` | Float | 否 | 否 | 否 | 标准化置信度或规则匹配分，不代表患病概率 |
| `mapping_method` | String(50) | 否 | 否 | 是 | `exact`, `alias`, `rule`, `manual`, `llm` |
| `is_manual_corrected` | Boolean | 否 | 否 | 是 | 默认 false |
| `corrected_by_user_id` | Integer | 否 | `users.id` | 否 | 修正人 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.9 `analysis_tasks` 分析任务表

用途：记录一次病例分析，包括排序、生成、校验的状态和版本。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `task_no` | String(80) | 否 | 否 | 是 | 唯一任务编号 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `requested_by_user_id` | Integer | 否 | `users.id` | 是 | 发起人 |
| `task_type` | String(50) | 否 | 否 | 是 | `candidate_ranking`, `kg_rag`, `validation`, `full_analysis` |
| `status` | String(30) | 否 | 否 | 是 | `queued`, `running`, `success`, `failed`, `degraded` |
| `input_snapshot` | JSON | 否 | 否 | 是 | 输入快照 |
| `error_message` | Text | 否 | 否 | 否 | 错误信息 |
| `generation_mode` | String(30) | 否 | 否 | 否 | `model`, `template` |
| `kg_version_id` | Integer | 否 | `kg_versions.id` | 是 | 图谱版本 |
| `prompt_version_id` | Integer | 否 | `prompt_versions.id` | 否 | Prompt 版本 |
| `model_version_id` | Integer | 否 | `model_versions.id` | 否 | 模型版本 |
| `algorithm_version_id` | Integer | 否 | `algorithm_versions.id` | 是 | 算法版本 |
| `started_at` | DateTime | 否 | 否 | 否 | 开始时间 |
| `finished_at` | DateTime | 否 | 否 | 否 | 结束时间 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.10 `candidate_diseases` 候选疾病表

用途：保存分析任务产生的候选疾病及评分分项。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `analysis_task_id` | Integer | 否 | `analysis_tasks.id` | 是 | 所属任务 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 冗余便于查询 |
| `rank_order` | Integer | 否 | 否 | 是 | 候选排序 |
| `disease_entity_id` | String(80) | 否 | 否 | 是 | CSV 疾病实体 ID |
| `disease_name_cn` | String(120) | 否 | 否 | 是 | 中文名 |
| `disease_name_en` | String(160) | 否 | 否 | 否 | 英文名 |
| `ham10000_label` | String(20) | 否 | 否 | 是 | 七类标签 |
| `total_score` | Float | 否 | 否 | 是 | 规则综合分，不是概率 |
| `feature_score` | Float | 否 | 否 | 是 | 特征匹配分 |
| `site_score` | Float | 否 | 否 | 是 | 发病部位匹配分 |
| `symptom_score` | Float | 否 | 否 | 是 | 症状匹配分 |
| `evidence_coverage_score` | Float | 否 | 否 | 是 | 有效证据覆盖分 |
| `conflict_penalty` | Float | 否 | 否 | 是 | 明确冲突特征惩罚 |
| `score_detail` | JSON | 否 | 否 | 否 | 分项详情 |
| `score_note` | Text | 否 | 否 | 是 | 必须说明非患病概率 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

主要约束：

- 同一 `analysis_task_id` 下 `rank_order` 唯一。
- `score_note` 应包含非概率说明。
- 评分公式为 `Score(d) = αMf + βMl + γMs + ηCe - λCf`。
- 风险提示不参与候选疾病排序，只在候选疾病形成后单独生成。
- 未填写、未知、未观察不能计入 `conflict_penalty`。
- 只有用户明确描述且与图谱证据矛盾时，才计入 `conflict_penalty`。

### 3.11 `evidence_paths` 证据路径表

用途：保存候选疾病关联的证据路径。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `candidate_disease_id` | Integer | 否 | `candidate_diseases.id` | 是 | 所属候选疾病 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `triple_id` | String(80) | 否 | 否 | 否 | 单跳兼容字段，V1.0 单跳路径可继续使用 |
| `head_entity_id` | String(80) | 否 | 否 | 否 | 单跳兼容字段：头实体 |
| `relation_en` | String(120) | 否 | 否 | 否 | 单跳兼容字段：英文关系 |
| `relation_cn` | String(120) | 否 | 否 | 否 | 单跳兼容字段：中文关系 |
| `tail_entity_id` | String(80) | 否 | 否 | 否 | 单跳兼容字段：尾实体 |
| `path_length` | Integer | 否 | 否 | 是 | 路径长度；单跳为 1 |
| `triple_ids` | JSON | 否 | 否 | 是 | 多步路径三元组 ID 序列 |
| `entity_ids` | JSON | 否 | 否 | 是 | 多步路径实体 ID 序列 |
| `relation_sequence` | JSON | 否 | 否 | 是 | 多步路径关系序列 |
| `path_rank` | Integer | 否 | 否 | 否 | 路径召回排序 |
| `retrieval_score` | Float | 否 | 否 | 否 | 路径召回得分 |
| `path_text` | Text | 否 | 否 | 是 | 展示路径 |
| `evidence_text` | Text | 否 | 否 | 否 | 证据文本 |
| `source_id` | String(80) | 否 | 否 | 否 | CSV 来源 ID |
| `source_name` | String(255) | 否 | 否 | 否 | 来源名称 |
| `support_type` | String(40) | 否 | 否 | 是 | `support`, `conflict`, `missing`, `background` |
| `weight` | Float | 否 | 否 | 否 | 路径权重 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

说明：

- V1.0 以单跳路径为主，`triple_id`、`head_entity_id`、`relation_en`、`tail_entity_id` 保留兼容。
- 多步路径使用 `path_length`、`triple_ids`、`entity_ids`、`relation_sequence` 表示完整路径。

### 3.12 `reports` 生成报告表

用途：保存辅助诊疗报告及版本。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `report_no` | String(80) | 否 | 否 | 是 | 唯一报告编号 |
| `report_group_no` | String(80) | 否 | 否 | 是 | 同一病例同一报告族编号 |
| `parent_report_id` | Integer | 否 | `reports.id` | 否 | 父报告版本，系统原始版本为空 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `analysis_task_id` | Integer | 否 | `analysis_tasks.id` | 是 | 来源任务 |
| `version_no` | Integer | 否 | 否 | 是 | 报告版本号 |
| `is_current` | Boolean | 否 | 否 | 是 | 是否当前版本 |
| `title` | String(255) | 否 | 否 | 是 | 标题 |
| `system_summary` | Text | 否 | 否 | 是 | 系统原始摘要 |
| `structured_content` | JSON | 否 | 否 | 是 | 结构化报告 |
| `markdown_content` | Text | 否 | 否 | 是 | 展示内容 |
| `disclaimer_text` | Text | 否 | 否 | 是 | 医学免责声明 |
| `status` | String(30) | 否 | 否 | 是 | `draft`, `pending_review`, `reviewed`, `exported`, `archived` |
| `export_path` | String(500) | 否 | 否 | 否 | 导出文件路径 |
| `created_by_user_id` | Integer | 否 | `users.id` | 是 | 创建人 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |
| `updated_at` | DateTime | 否 | 否 | 是 | 更新时间 |

主要约束：

- 唯一约束：`UNIQUE(case_id, report_group_no, version_no)`。
- 同一 `report_group_no` 下 `version_no` 递增。
- 系统原始报告保存为该报告族的初始版本，`parent_report_id` 为空。
- 医生修订报告保存为新版本，`parent_report_id` 指向上一版或系统原始版本。
- 系统原始输出和医生修订版本不得互相覆盖；切换当前报告只更新 `is_current`。

### 3.13 `medical_claims` 医学声明表

用途：保存生成报告中拆分出的可核查医学声明。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `report_id` | Integer | 否 | `reports.id` | 是 | 所属报告 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `claim_text` | Text | 否 | 否 | 是 | 原子声明 |
| `claim_type` | String(50) | 否 | 否 | 是 | `manifestation`, `risk`, `exam`, `advice`, `differential`, `other` |
| `mapped_disease_entity_id` | String(80) | 否 | 否 | 否 | 映射疾病 |
| `mapped_relation_en` | String(120) | 否 | 否 | 否 | 映射关系 |
| `mapped_tail_entity_id` | String(80) | 否 | 否 | 否 | 映射尾实体 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.14 `claim_validation_results` 声明校验结果表

用途：保存声明与图谱证据匹配结果。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `claim_id` | Integer | 否 | `medical_claims.id` | 是 | 所属声明 |
| `report_id` | Integer | 否 | `reports.id` | 是 | 所属报告 |
| `validation_status` | String(40) | 否 | 否 | 是 | `supported`, `partially_supported`, `unsupported`, `not_verifiable` |
| `matched_triple_ids` | JSON | 否 | 否 | 否 | 匹配三元组 ID 列表 |
| `matched_evidence_path_ids` | JSON | 否 | 否 | 否 | 匹配证据路径表 ID 列表 |
| `reason` | Text | 否 | 否 | 是 | 校验说明 |
| `validator_version` | String(80) | 否 | 否 | 是 | 校验器版本 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.15 `report_validation_metrics` 报告校验指标表

用途：保存报告级证据一致性指标。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `report_id` | Integer | 否 | `reports.id` | 是 | 唯一 |
| `observation_evidence_hit_rate` | Float | 否 | 否 | 否 | OEHR，观察证据命中率 |
| `evidence_coverage_rate` | Float | 否 | 否 | 否 | 证据覆盖率 |
| `unsupported_claim_rate` | Float | 否 | 否 | 否 | 无支持声明比例 |
| `path_consistency_score` | Float | 否 | 否 | 否 | 路径一致性分 |
| `matched_observation_count` | Integer | 否 | 否 | 是 | 命中图谱证据的有效观察锚点数 |
| `verifiable_observation_count` | Integer | 否 | 否 | 是 | 可标准化的有效观察锚点总数 |
| `supported_claim_count` | Integer | 否 | 否 | 是 | supported 声明数 |
| `partially_supported_claim_count` | Integer | 否 | 否 | 是 | partially_supported 声明数 |
| `unsupported_claim_count` | Integer | 否 | 否 | 是 | unsupported 声明数 |
| `not_verifiable_claim_count` | Integer | 否 | 否 | 是 | not_verifiable 声明数，单独记录 |
| `mapped_claim_count` | Integer | 否 | 否 | 是 | 成功映射为结构化路径的声明总数 |
| `path_consistent_claim_count` | Integer | 否 | 否 | 是 | 疾病、关系、尾实体均一致的声明数 |
| `used_evidence_type_count` | Integer | 否 | 否 | 是 | 输出实际使用的相关证据类型数 |
| `available_evidence_type_count` | Integer | 否 | 否 | 是 | 当前任务可用的相关证据类型数 |
| `metric_definition_version` | String(80) | 否 | 否 | 是 | 指标定义版本 |
| `metric_detail` | JSON | 否 | 否 | 否 | 指标明细 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

指标定义：

- `OEHR = matched_observation_count / verifiable_observation_count`。
- `UCR = unsupported_claim_count / 可验证医学声明总数`，其中可验证医学声明总数为 `supported_claim_count + partially_supported_claim_count + unsupported_claim_count`；`not_verifiable` 不得自动算作 `supported`，需要通过 `not_verifiable_claim_count` 单独记录。
- `PCS = path_consistent_claim_count / mapped_claim_count`。
- `ECR = used_evidence_type_count / available_evidence_type_count`。

### 3.16 `doctor_reviews` 医生审核表

用途：保存医生对候选结果和报告的审核意见。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `report_id` | Integer | 否 | `reports.id` | 是 | 所属报告 |
| `doctor_user_id` | Integer | 否 | `users.id` | 是 | 审核医生 |
| `status` | String(30) | 否 | 否 | 是 | `draft`, `submitted` |
| `decision` | String(30) | 否 | 否 | 否 | `approved`, `revised`, `rejected`, `needs_followup` |
| `final_diagnosis_text` | Text | 否 | 否 | 否 | 医生录入或确认的最终诊断/方向 |
| `followup_exam_suggestion` | Text | 否 | 否 | 否 | 后续检查方向 |
| `doctor_comment` | Text | 否 | 否 | 否 | 医生意见 |
| `candidate_adjustments` | JSON | 否 | 否 | 否 | 排序调整和删除记录 |
| `revised_report_content` | Text | 否 | 否 | 否 | 医生修订版 |
| `submitted_at` | DateTime | 否 | 否 | 否 | 提交时间，仅最终提交时填写 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |
| `updated_at` | DateTime | 否 | 否 | 是 | 更新时间 |

主要约束：

- 只有医生角色可提交。
- 保留系统原始输出，不覆盖 `reports.system_summary`。
- 草稿审核记录 `submitted_at` 为空；只有 `status=submitted` 时填写。

### 3.17 `feedback` 反馈表

用途：保存医生或患者对辅助结果的反馈。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `case_id` | Integer | 否 | `cases.id` | 是 | 所属病例 |
| `report_id` | Integer | 否 | `reports.id` | 否 | 所属报告 |
| `user_id` | Integer | 否 | `users.id` | 是 | 反馈人 |
| `feedback_type` | String(50) | 否 | 否 | 是 | `useful`, `not_useful`, `incorrect`, `unsafe`, `other` |
| `rating` | Integer | 否 | 否 | 否 | 1-5 |
| `comment` | Text | 否 | 否 | 否 | 反馈内容 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.18 `kg_versions` 图谱版本表

用途：记录使用的 CSV 图谱版本。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `version_code` | String(80) | 否 | 否 | 是 | 唯一 |
| `entity_csv_path` | String(500) | 否 | 否 | 是 | 实体 CSV 路径 |
| `triple_csv_path` | String(500) | 否 | 否 | 是 | 三元组 CSV 路径 |
| `source_csv_path` | String(500) | 否 | 否 | 是 | 来源 CSV 路径 |
| `entity_count` | Integer | 否 | 否 | 否 | 实体数 |
| `triple_count` | Integer | 否 | 否 | 否 | 三元组数 |
| `source_count` | Integer | 否 | 否 | 否 | 来源数 |
| `checksum` | String(128) | 否 | 否 | 否 | CSV 快照校验 |
| `is_active` | Boolean | 否 | 否 | 是 | 是否当前版本 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.19 `prompt_versions` Prompt 版本表

用途：管理 KG-RAG、患者解释和校验 Prompt。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `version_code` | String(80) | 否 | 否 | 是 | 唯一 |
| `prompt_type` | String(50) | 否 | 否 | 是 | `doctor_kg_rag`, `patient_explain`, `claim_validation` |
| `template_path` | String(500) | 否 | 否 | 否 | 模板文件路径 |
| `template_content` | Text | 否 | 否 | 否 | 可选快照 |
| `status` | String(30) | 否 | 否 | 是 | `draft`, `active`, `archived` |
| `created_by_user_id` | Integer | 否 | `users.id` | 否 | 创建人 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.20 `model_versions` 模型版本表

用途：记录模型配置，不保存明文密钥。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `version_code` | String(80) | 否 | 否 | 是 | 唯一 |
| `provider` | String(80) | 否 | 否 | 是 | 模型服务商或 `template` |
| `model_name` | String(120) | 否 | 否 | 是 | 模型名称 |
| `config_json` | JSON | 否 | 否 | 否 | 不含密钥 |
| `is_active` | Boolean | 否 | 否 | 是 | 是否启用 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.21 `algorithm_versions` 算法版本表

用途：记录排序、召回、校验算法版本。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `version_code` | String(80) | 否 | 否 | 是 | 唯一 |
| `algorithm_type` | String(80) | 否 | 否 | 是 | `ranking`, `retrieval`, `validation`, `full_pipeline` |
| `description` | Text | 否 | 否 | 否 | 说明 |
| `parameters_json` | JSON | 否 | 否 | 否 | alpha/beta/gamma 等参数 |
| `is_active` | Boolean | 否 | 否 | 是 | 是否启用 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.22 `experiment_runs` 实验任务表

用途：记录纯 LLM、普通 RAG、KG-RAG、KG-RAG+校验等实验运行。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `run_no` | String(80) | 否 | 否 | 是 | 唯一 |
| `experiment_name` | String(255) | 否 | 否 | 是 | 实验名称 |
| `method_type` | String(80) | 否 | 否 | 是 | `llm`, `rag`, `kg_rag`, `kg_rag_validation` |
| `dataset_path` | String(500) | 否 | 否 | 否 | 测试集路径 |
| `status` | String(30) | 否 | 否 | 是 | `draft`, `running`, `completed`, `failed` |
| `kg_version_id` | Integer | 否 | `kg_versions.id` | 否 | 图谱版本 |
| `prompt_version_id` | Integer | 否 | `prompt_versions.id` | 否 | Prompt 版本 |
| `model_version_id` | Integer | 否 | `model_versions.id` | 否 | 模型版本 |
| `algorithm_version_id` | Integer | 否 | `algorithm_versions.id` | 否 | 算法版本 |
| `summary_metrics` | JSON | 否 | 否 | 否 | 指标汇总 |
| `created_by_user_id` | Integer | 否 | `users.id` | 是 | 创建人 |
| `started_at` | DateTime | 否 | 否 | 否 | 开始时间 |
| `finished_at` | DateTime | 否 | 否 | 否 | 结束时间 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.23 `experiment_cases` 实验样例结果表

用途：保存单个实验样例的输出和指标。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `experiment_run_id` | Integer | 否 | `experiment_runs.id` | 是 | 所属实验 |
| `case_id_text` | String(80) | 否 | 否 | 是 | CSV 样例 ID |
| `candidate_disease` | String(120) | 否 | 否 | 是 | 候选疾病 |
| `ham10000_label` | String(20) | 否 | 否 | 是 | 标签 |
| `input_text` | Text | 否 | 否 | 是 | 输入观察 |
| `output_text` | Text | 否 | 否 | 否 | 输出内容 |
| `metrics_json` | JSON | 否 | 否 | 否 | 指标 |
| `output_file_path` | String(500) | 否 | 否 | 否 | 输出文件 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

### 3.24 `operation_logs` 操作日志表

用途：记录登录、病例访问、报告审核、知识修改、模型调用等审计事件。

| 字段 | 类型 | 主键 | 外键 | 必填 | 约束/说明 |
|---|---|---|---|---|---|
| `id` | Integer | 是 | 否 | 是 | 自增 |
| `request_id` | String(120) | 否 | 否 | 是 | 请求 ID |
| `user_id` | Integer | 否 | `users.id` | 否 | 操作用户 |
| `action` | String(120) | 否 | 否 | 是 | 操作类型 |
| `resource_type` | String(80) | 否 | 否 | 否 | 资源类型 |
| `resource_id` | String(80) | 否 | 否 | 否 | 资源 ID |
| `ip_address` | String(80) | 否 | 否 | 否 | IP |
| `user_agent` | String(255) | 否 | 否 | 否 | UA |
| `status` | String(30) | 否 | 否 | 是 | `success`, `failed` |
| `message` | Text | 否 | 否 | 否 | 可读说明 |
| `metadata_json` | JSON | 否 | 否 | 否 | 避免记录完整敏感文本 |
| `created_at` | DateTime | 否 | 否 | 是 | 创建时间 |

## 4. 主要关系

```text
users -- user_roles -- roles
users -- cases
anonymous_patients -- cases
cases -- clinical_observations
cases -- lesion_images
cases -- semantic_anchors
cases -- analysis_tasks
analysis_tasks -- candidate_diseases
candidate_diseases -- evidence_paths
analysis_tasks -- reports
reports -- medical_claims
medical_claims -- claim_validation_results
reports -- report_validation_metrics
reports -- doctor_reviews
cases -- feedback
kg_versions -- analysis_tasks
prompt_versions -- analysis_tasks
model_versions -- analysis_tasks
algorithm_versions -- analysis_tasks
experiment_runs -- experiment_cases
```

## 5. 索引建议

- `users.username`
- `anonymous_patients.patient_code`
- `cases.case_no`
- `cases.status`
- `cases.patient_id`
- `cases.created_by_user_id`
- `semantic_anchors.case_id`
- `semantic_anchors.normalized_entity_id`
- `analysis_tasks.case_id`
- `candidate_diseases.analysis_task_id`
- `candidate_diseases.disease_entity_id`
- `evidence_paths.triple_id`
- `reports.case_id`
- `reports.report_no`
- `operation_logs.request_id`
- `operation_logs.user_id`
- `operation_logs.created_at`

## 6. 数据安全与审计约束

- 密码仅保存哈希。
- API Key 不进入数据库明文字段，不返回前端。
- 患者使用匿名编号。
- 操作日志避免记录完整敏感文本。
- 报告和医生审核必须保留原始系统输出和医生修订输出。
- 未经授权用户不能访问其他患者或医生病例。
- 知识管理员不能修改医生最终诊断。
