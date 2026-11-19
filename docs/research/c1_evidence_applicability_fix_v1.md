# C1 医学证据适用性最小修复记录

本轮为六例生成可行性试验前的限定修复，不是医学专家认证，不启动生成实验。
保留上一轮病例编号隔离；患者原始字段、三态、映射、评分公式与权重均未修改。

## 来源和变更依据

- TRI_030：本地证据及上轮读取的 [DermNet BCC](https://dermnetnz.org/topics/basal-cell-carcinoma) 的 Nodular BCC 小节仅支持“面部 BCC 中结节型最常见”的类型分布，不能直接推出“BCC 常见于面部”。未补造替代医学事实：在独立元数据中标为 pending_source_verification，所有包含该边的路径过滤，原 triples.csv 行仍保留供审计。不将其伪装为可靠背景。
- TRI_006、TRI_013：上轮读取的 [DermNet Melanoma](https://dermnetnz.org/topics/melanoma) 临床表现小节明确为新西兰人群：男性常见背部（约40%），女性常见腿部（约35%），且可发生在其他部位。结构化保存 gender、population_context 条件、来源URL及范围说明。2022-10 是网页所示日期，不是仓库原始抽取版本。
- TRI_034 的本地 evidence_text 指脂溢性角化病；TRI_062 的本地文本及上轮读取的 [DermNet Lichenoid keratosis](https://dermnetnz.org/topics/lichenoid-keratosis) 临床表现小节指扁平苔藓样角化病。给两端分别标注具体知识对象，仅阻断已明确不兼容的 TRI_034 → TRI_062，保留独立边及其他路径。TRI_034 准确外部出处仍待补齐，不宣称完成来源认证。
- 上述网页内容来自同一会话上一轮审计的只读核查；本轮尝试重新打开网页时连接失败。因此没有宣称本轮取得新来源，也没有覆盖已有历史来源记录。元数据 checked_on 记录前次核查日期 2026-11-19。

## 条件判断与输入边界

`not_required`：当前未标注额外适用条件，不表示经过全面医学审核。
`satisfied`：全部已标注条件满足；仍需原有可靠 present 实体匹配，才能直接支持。
`not_satisfied`：至少一个已知条件不匹配；即使其他条件未知，也保留已知的不匹配及未知原因。
`unknown`：没有已知不匹配，但至少一项必要条件缺失。

`population_context` 是调用方依据可核查材料确认的统计适用人群，不等于国籍、出生地或族裔。仅显式值 NEW ZEALAND 与对应范围匹配；当前六例没有该字段，系统不补填。测试中的符合范围条件是合成输入，不冒充原始 PAD 信息。
统计条件不满足/未知：直接路径为 BACKGROUND_ONLY；鉴别路径继续 DIFFERENTIAL_ONLY，但仅可作范围受限的一般鉴别说明。C2 不给这些路径写入 matched_fact_ids，保留事实、条件状态、原因及来源URL。C3/C4收到同一限制信息，不改变其生成/核验核心策略。
条件不满足不推导为排除疾病；统计部位比例不转换为诊断概率。

## 修改前后 Top-5

S=PATIENT_SUPPORT，B=BACKGROUND_ONLY，D=DIFFERENTIAL_ONLY。
每项依次为路径ID、角色/适用性状态/原评分。顺序即实际排名。修改前未做适用性评估。

| 病例 | 候选疾病 | 修改前 Top-5 | 修改后 Top-5 | 可用路径数 |
| --- | --- | --- | --- | --- |
| PAD_BCC_001 | 基底细胞癌 | `PATH_TRI_030` S/未评估/4.0<br>`PATH_TRI_031` S/未评估/3.9<br>`PATH_TRI_034_TRI_062` D/未评估/3.45<br>`PATH_TRI_035_TRI_007` D/未评估/3.45<br>`PATH_TRI_035_TRI_014` D/未评估/3.45 | `PATH_TRI_031` S/not_required/3.9<br>`PATH_TRI_035_TRI_007` D/not_required/3.45<br>`PATH_TRI_035_TRI_014` D/not_required/3.45<br>`PATH_TRI_025` B/not_required/2.5<br>`PATH_TRI_026` B/not_required/2.5 | 36 → 34 |
| PAD_BCC_001 | 黑色素瘤 | `PATH_TRI_007` S/未评估/3.9<br>`PATH_TRI_014` S/未评估/3.9<br>`PATH_TRI_001` B/未评估/2.5<br>`PATH_TRI_002` B/未评估/2.5<br>`PATH_TRI_003` B/未评估/2.5 | `PATH_TRI_007` S/not_required/3.9<br>`PATH_TRI_014` S/not_required/3.9<br>`PATH_TRI_001` B/not_required/2.5<br>`PATH_TRI_002` B/not_required/2.5<br>`PATH_TRI_003` B/not_required/2.5 | 21 → 21 |
| PAD_BCC_002 | 基底细胞癌 | `PATH_TRI_030` S/未评估/4.0<br>`PATH_TRI_031` S/未评估/3.9<br>`PATH_TRI_034_TRI_062` D/未评估/3.45<br>`PATH_TRI_035_TRI_007` D/未评估/3.45<br>`PATH_TRI_035_TRI_014` D/未评估/3.45 | `PATH_TRI_031` S/not_required/3.9<br>`PATH_TRI_035_TRI_007` D/not_required/3.45<br>`PATH_TRI_035_TRI_014` D/not_required/3.45<br>`PATH_TRI_025` B/not_required/2.5<br>`PATH_TRI_026` B/not_required/2.5 | 36 → 34 |
| PAD_BCC_002 | 黑色素瘤 | `PATH_TRI_007` S/未评估/3.9<br>`PATH_TRI_014` S/未评估/3.9<br>`PATH_TRI_001` B/未评估/2.5<br>`PATH_TRI_002` B/未评估/2.5<br>`PATH_TRI_003` B/未评估/2.5 | `PATH_TRI_007` S/not_required/3.9<br>`PATH_TRI_014` S/not_required/3.9<br>`PATH_TRI_001` B/not_required/2.5<br>`PATH_TRI_002` B/not_required/2.5<br>`PATH_TRI_003` B/not_required/2.5 | 21 → 21 |
| PAD_MEL_001 | 黑色素瘤 | `PATH_TRI_006` S/未评估/4.0<br>`PATH_TRI_014` S/未评估/3.9<br>`PATH_TRI_001` B/未评估/2.5<br>`PATH_TRI_002` B/未评估/2.5<br>`PATH_TRI_003` B/未评估/2.5 | `PATH_TRI_006` B/not_satisfied/4.0<br>`PATH_TRI_014` S/not_required/3.9<br>`PATH_TRI_001` B/not_required/2.5<br>`PATH_TRI_002` B/not_required/2.5<br>`PATH_TRI_003` B/not_required/2.5 | 21 → 21 |
| PAD_MEL_001 | 黑色素细胞痣 | `PATH_TRI_021_TRI_006` D/未评估/3.55<br>`PATH_TRI_021_TRI_014` D/未评估/3.45<br>`PATH_TRI_015` B/未评估/2.5<br>`PATH_TRI_016` B/未评估/2.5<br>`PATH_TRI_017` B/未评估/2.5 | `PATH_TRI_021_TRI_006` D/not_satisfied/3.55<br>`PATH_TRI_021_TRI_014` D/not_required/3.45<br>`PATH_TRI_015` B/not_required/2.5<br>`PATH_TRI_016` B/not_required/2.5<br>`PATH_TRI_017` B/not_required/2.5 | 21 → 21 |
| PAD_MEL_002 | 黑色素瘤 | `PATH_TRI_006` S/未评估/4.0<br>`PATH_TRI_014` S/未评估/3.9<br>`PATH_TRI_001` B/未评估/2.5<br>`PATH_TRI_002` B/未评估/2.5<br>`PATH_TRI_003` B/未评估/2.5 | `PATH_TRI_006` B/unknown/4.0<br>`PATH_TRI_014` S/not_required/3.9<br>`PATH_TRI_001` B/not_required/2.5<br>`PATH_TRI_002` B/not_required/2.5<br>`PATH_TRI_003` B/not_required/2.5 | 21 → 21 |
| PAD_MEL_002 | 黑色素细胞痣 | `PATH_TRI_021_TRI_006` D/未评估/3.55<br>`PATH_TRI_021_TRI_014` D/未评估/3.45<br>`PATH_TRI_015` B/未评估/2.5<br>`PATH_TRI_016` B/未评估/2.5<br>`PATH_TRI_017` B/未评估/2.5 | `PATH_TRI_021_TRI_006` D/unknown/3.55<br>`PATH_TRI_021_TRI_014` D/not_required/3.45<br>`PATH_TRI_015` B/not_required/2.5<br>`PATH_TRI_016` B/not_required/2.5<br>`PATH_TRI_017` B/not_required/2.5 | 21 → 21 |
| PAD_NEV_001 | 黑色素细胞痣 | `PATH_TRI_015` B/未评估/2.5<br>`PATH_TRI_016` B/未评估/2.5<br>`PATH_TRI_017` B/未评估/2.5<br>`PATH_TRI_018` B/未评估/2.5<br>`PATH_TRI_021_TRI_001` D/未评估/2.05 | `PATH_TRI_015` B/not_required/2.5<br>`PATH_TRI_016` B/not_required/2.5<br>`PATH_TRI_017` B/not_required/2.5<br>`PATH_TRI_018` B/not_required/2.5<br>`PATH_TRI_021_TRI_001` D/not_required/2.05 | 21 → 21 |
| PAD_NEV_001 | 黑色素瘤 | `PATH_TRI_001` B/未评估/2.5<br>`PATH_TRI_002` B/未评估/2.5<br>`PATH_TRI_003` B/未评估/2.5<br>`PATH_TRI_004` B/未评估/2.5<br>`PATH_TRI_005` B/未评估/2.5 | `PATH_TRI_001` B/not_required/2.5<br>`PATH_TRI_002` B/not_required/2.5<br>`PATH_TRI_003` B/not_required/2.5<br>`PATH_TRI_004` B/not_required/2.5<br>`PATH_TRI_005` B/not_required/2.5 | 21 → 21 |
| PAD_NEV_002 | 黑色素细胞痣 | `PATH_TRI_021_TRI_006` D/未评估/3.55<br>`PATH_TRI_015` B/未评估/2.5<br>`PATH_TRI_016` B/未评估/2.5<br>`PATH_TRI_017` B/未评估/2.5<br>`PATH_TRI_018` B/未评估/2.5 | `PATH_TRI_021_TRI_006` D/unknown/3.55<br>`PATH_TRI_015` B/not_required/2.5<br>`PATH_TRI_016` B/not_required/2.5<br>`PATH_TRI_017` B/not_required/2.5<br>`PATH_TRI_018` B/not_required/2.5 | 21 → 21 |
| PAD_NEV_002 | 黑色素瘤 | `PATH_TRI_006` S/未评估/4.0<br>`PATH_TRI_001` B/未评估/2.5<br>`PATH_TRI_002` B/未评估/2.5<br>`PATH_TRI_003` B/未评估/2.5<br>`PATH_TRI_004` B/未评估/2.5 | `PATH_TRI_006` B/unknown/4.0<br>`PATH_TRI_001` B/not_required/2.5<br>`PATH_TRI_002` B/not_required/2.5<br>`PATH_TRI_003` B/not_required/2.5<br>`PATH_TRI_004` B/not_required/2.5 | 21 → 21 |

## 验证范围与解释

- BCC候选：过滤 PATH_TRI_030 和 PATH_TRI_034_TRI_062，36条变34条；原第6、7条背景路径递补Top-5。变化来自有效性过滤，不是重新调分。
- MEL/NEV候选：路径顺序、分数不变；包含TRI_006/013的路径新增限制状态，直接匹配路径可能降为背景。不得把排名第一解释为医学适用性最强。
- 12个条件的全部原有患者事实（包括匿名编号）、语义锚点以及所有保留路径的 total_score 与本轮修改前逐项相等。不相关路径的分项分数、内容、角色和相对顺序由修改前摘要锁定。
- `experiments/validate_c1_applicability.py` 固定修复前不相关路径摘要；`validate_patient_id_isolation.py` 更新整体结构摘要，但保留全部编号隔离、六例双候选及C3/C4模拟引用检查，未删除泄漏测试。
- 保留原始三元组而用默认必读的元数据文件施加限制。缺少/损坏文件报错，不能悄悄恢复未限制角色。

## 限制与结论

本轮离线检查：语义锚点7、路径排序6、C1事实14、C1集成7、C2台账10、C3生成15、C4核验30、编号隔离3、新增适用性7、纯LLM基线3、普通RAG基线4，共106项通过。全部使用确定性代码或模拟客户端，未调用真实模型。`git diff --check` 通过。既有旧版KG-RAG测试模拟对象不兼容问题不包含在以上通过数中。

可以进入六例小规模生成可行性试验，限于验证证据引用、角色与限制信息传递、证据不足表述，不代表真实模型质量或临床有效性已证明。本轮没有运行生成试验。
TRI_030 来源关系仍待核实，但已经从有效证据中隔离；其他未审计知识、来源版本完整性、病例级错误候选医学合理性仍是局限，不能据本次补丁宣称全图通过医学审核。
历史结果未迁移，不与修复后结果混作同一方法条件；旧的 manual_check_c2.py 硬编码旧编号和 validate_kg_rag_pipeline.py 旧模拟对象缺字段的问题属于上轮已报告事项，本轮不扩大修改。
