# 任务四正式测试病例集规范 V2.0

## 1. 文档目的

本文档用于规范毕业论文中纯 LLM、普通 RAG 和 KG-RAG 三种方法的正式对照实验病例集。

正式病例集计划包含 140 条病例，具体构成为：

- 7 类皮肤疾病；
- 每类疾病 20 条病例；
- 每类疾病包含 5 种病例类型；
- 每种病例类型包含 4 条病例。

现有文件：

`experiments/cases/task4_cases_v1.json`

仅包含 7 条病例，用于程序联调和冒烟测试，不作为论文正式实验数据。

正式病例集文件统一命名为：

`experiments/cases/task4_cases_v2.json`

---

## 2. 疾病类别

正式测试集覆盖以下 7 类疾病：

| 序号 | 疾病标准名称 | 疾病缩写 |
|---:|---|---|
| 1 | 黑色素瘤 | MEL |
| 2 | 黑色素细胞痣 | NV |
| 3 | 基底细胞癌 | BCC |
| 4 | 光化性角化病/表皮内癌 | AKIEC |
| 5 | 良性角化样病变 | BKL |
| 6 | 皮肤纤维瘤 | DF |
| 7 | 血管性皮损 | VASC |

正式病例中的 `true_label` 和 `candidate_disease` 应优先使用上述标准疾病名称。

以下名称可以作为用户自然语言表达或系统鲁棒性测试中的同义名称：

| 非标准名称 | 图谱标准名称 |
|---|---|
| 良性角化性病变 | 良性角化样病变 |
| 良性角化病变 | 良性角化样病变 |
| 血管性病变 | 血管性皮损 |
| 血管病变 | 血管性皮损 |

正式数据统计时必须统一映射到图谱标准名称。

---

## 3. 病例数量与类型分布

每类疾病包含 20 条病例，分为以下 5 种病例类型：

| 病例类型 | 中文名称 | 每类数量 | 7 类合计 |
|---|---|---:|---:|
| `typical_positive` | 典型支持型 | 4 | 28 |
| `partial_support` | 部分支持型 | 4 | 28 |
| `evidence_insufficient` | 证据不足型 | 4 | 28 |
| `differential_confusion` | 鉴别混淆型 | 4 | 28 |
| `conflict_difficult` | 冲突困难型 | 4 | 28 |
| 合计 | — | 20 | 140 |

---

## 4. 病例类型定义

### 4.1 典型支持型

英文标识：

`typical_positive`

病例要求：

1. `candidate_disease` 与 `true_label` 一致；
2. 包含至少 3 个候选疾病的典型观察特征；
3. 至少包含 1 个皮损形态特征；
4. 可以包含典型发病部位、病程变化或伴随表现；
5. 不加入明显冲突特征；
6. 当前知识图谱中应存在较充分的支持证据。

预期系统行为：

1. 能识别多个典型观察特征；
2. 能检索到与候选疾病相关的支持证据；
3. KG-RAG 应返回高相关度证据路径；
4. 回答应保持医学谨慎，不得表述为已经确诊。

建议难度：

`easy` 或 `medium`

建议证据状态：

`sufficient`

---

### 4.2 部分支持型

英文标识：

`partial_support`

病例要求：

1. `candidate_disease` 与 `true_label` 一般保持一致；
2. 只包含 1 至 2 个相对明确的支持特征；
3. 其余描述应为非特异性或模糊特征；
4. 缺少形成充分判断所需的完整信息；
5. 不加入明显与候选疾病冲突的特征。

预期系统行为：

1. 能识别有限的支持证据；
2. 明确指出当前证据不充分；
3. 避免使用确定性诊断表达；
4. 能指出仍需补充的信息。

建议难度：

`medium`

建议证据状态：

`partial`

---

### 4.3 证据不足型

英文标识：

`evidence_insufficient`

病例要求：

1. `candidate_disease` 可以与 `true_label` 一致；
2. 观察文本只包含宽泛或非特异性表现；
3. 缺少关键皮损形态；
4. 缺少明确部位、病程或检查结果；
5. 不提供足以支持候选疾病的核心特征。

预期系统行为：

1. 不应强行建立充分支持关系；
2. 应明确指出证据不足；
3. `evidence_gap` 中应列出缺失信息；
4. 应建议进一步检查或皮肤科面诊；
5. 不得输出确定性诊断结论。

建议难度：

`medium`

建议证据状态：

`insufficient`

---

### 4.4 鉴别混淆型

英文标识：

`differential_confusion`

病例要求：

1. `candidate_disease` 可以与 `true_label` 不同；
2. 观察文本包含另一个疾病的典型或部分典型特征；
3. 候选疾病与真实疾病之间应具有一定鉴别可能；
4. 仅凭观察信息难以完全确定；
5. 需要结合皮肤镜或病理检查进一步判断。

预期系统行为：

1. 能识别候选疾病与观察结果之间的不完全匹配；
2. 能提出合理的鉴别诊断；
3. 不得忽略明显指向其他疾病的特征；
4. 能说明需要哪些检查进一步鉴别。

建议难度：

`hard`

建议证据状态：

`conflicting`

---

### 4.5 冲突困难型

英文标识：

`conflict_difficult`

病例要求：

1. 同时包含支持候选疾病和不支持候选疾病的特征；
2. 或者包含彼此矛盾的形态、部位、病程或症状描述；
3. 或者观察结果与候选疾病只有局部重合；
4. 病例必须具有明显的不确定性；
5. 不应通过单一特征直接得出结论。

预期系统行为：

1. 同时说明支持证据与冲突证据；
2. 不得只选择性引用支持候选疾病的内容；
3. 应明确提示不确定性；
4. 应在 `evidence_gap` 中说明冲突点；
5. 不得输出确定性诊断结论。

建议难度：

`hard`

建议证据状态：

`conflicting`

---

## 5. 病例编号规范

每条病例必须具有唯一的 `case_id`。

编号格式：

`CASE_<疾病缩写>_<病例类型缩写>_<序号>`

疾病缩写如下：

| 疾病 | 缩写 |
|---|---|
| 黑色素瘤 | MEL |
| 黑色素细胞痣 | NV |
| 基底细胞癌 | BCC |
| 光化性角化病/表皮内癌 | AKIEC |
| 良性角化样病变 | BKL |
| 皮肤纤维瘤 | DF |
| 血管性皮损 | VASC |

病例类型缩写如下：

| 病例类型 | 缩写 |
|---|---|
| `typical_positive` | TP |
| `partial_support` | PS |
| `evidence_insufficient` | EI |
| `differential_confusion` | DC |
| `conflict_difficult` | CD |

编号示例：

- `CASE_BCC_TP_001`
- `CASE_BCC_PS_001`
- `CASE_MEL_DC_003`
- `CASE_VASC_CD_004`

同一种疾病、同一种病例类型下的序号从 `001` 开始。

---

## 6. 病例字段规范

每条病例必须包含以下字段。

### 6.1 case_id

含义：

病例唯一编号。

类型：

字符串。

示例：

`"case_id": "CASE_BCC_TP_001"`

要求：

1. 不得为空；
2. 在整个病例集中必须唯一；
3. 必须符合规定的编号格式。

---

### 6.2 true_label

含义：

病例预设的真实疾病类别。

类型：

字符串。

示例：

`"true_label": "基底细胞癌"`

要求：

必须是 7 个标准疾病名称之一。

---

### 6.3 candidate_disease

含义：

提供给纯 LLM、普通 RAG 和 KG-RAG 进行解释的候选疾病。

类型：

字符串。

示例：

`"candidate_disease": "基底细胞癌"`

规则：

1. 典型支持型通常与 `true_label` 一致；
2. 部分支持型通常与 `true_label` 一致；
3. 证据不足型通常与 `true_label` 一致；
4. 鉴别混淆型可以与 `true_label` 不同；
5. 冲突困难型可以与 `true_label` 不同。

---

### 6.4 observation_text

含义：

发送给三种实验方法的完整观察文本。

类型：

字符串。

示例：

`"observation_text": "患者面部出现光亮的珍珠样结节，表面可见细小血管，近半年缓慢增大。"`

要求：

1. 只描述患者可观察到的信息；
2. 不直接写出诊断结论；
3. 不使用“已经确诊”“医生诊断为”等表达；
4. 可以包含皮损形态、颜色、部位、症状和变化；
5. 三种方法必须使用完全相同的 `observation_text`。

---

### 6.5 lesion_features

含义：

结构化皮损特征。

类型：

字符串数组。

示例：

    "lesion_features": [
      "珍珠样结节",
      "表面毛细血管扩张",
      "缓慢生长"
    ]

要求：

1. 每项只描述一个主要特征；
2. 不得写入诊断结论；
3. 至少包含一个皮损特征；
4. 证据不足型病例也应记录观察到的非特异性特征。

---

### 6.6 anatomical_site

含义：

皮损发生部位。

类型：

字符串。

示例：

`"anatomical_site": "面部"`

没有明确部位时填写：

`"anatomical_site": ""`

---

### 6.7 symptoms

含义：

患者自觉症状或伴随表现。

类型：

字符串数组。

示例：

    "symptoms": [
      "轻度瘙痒",
      "偶有出血"
    ]

没有自觉症状时填写：

`"symptoms": []`

---

### 6.8 duration_change

含义：

病程、持续时间或近期变化情况。

类型：

字符串。

示例：

`"duration_change": "近半年缓慢增大"`

没有相关信息时填写：

`"duration_change": ""`

---

### 6.9 difficulty_level

含义：

病例难度。

类型：

字符串。

允许值：

- `easy`
- `medium`
- `hard`

建议分配：

| 病例类型 | 推荐难度 |
|---|---|
| `typical_positive` | `easy` 或 `medium` |
| `partial_support` | `medium` |
| `evidence_insufficient` | `medium` |
| `differential_confusion` | `hard` |
| `conflict_difficult` | `hard` |

---

### 6.10 case_type

含义：

病例设计类型。

类型：

字符串。

允许值：

- `typical_positive`
- `partial_support`
- `evidence_insufficient`
- `differential_confusion`
- `conflict_difficult`

---

### 6.11 expected_concepts

含义：

根据病例设计，预计回答或检索证据需要覆盖的关键概念。

类型：

字符串数组。

示例：

    "expected_concepts": [
      "珍珠样结节",
      "表面毛细血管扩张",
      "面部",
      "缓慢生长"
    ]

用途：

1. 用于自动评价；
2. 不发送给模型；
3. 用于计算观察概念覆盖率和证据命中情况。

要求：

不得为空。

---

### 6.12 supporting_concepts

含义：

支持 `candidate_disease` 的观察概念。

类型：

字符串数组。

示例：

    "supporting_concepts": [
      "珍珠样结节",
      "表面毛细血管扩张",
      "面部"
    ]

规则：

1. 典型支持型应包含多个支持概念；
2. 部分支持型一般包含 1 至 2 个支持概念；
3. 证据不足型可以为空或只包含弱支持概念；
4. 鉴别混淆型和冲突困难型可以同时包含支持概念与冲突概念。

---

### 6.13 conflicting_concepts

含义：

与 `candidate_disease` 不一致，或者更倾向于其他疾病的观察概念。

类型：

字符串数组。

示例：

    "conflicting_concepts": [
      "明显不对称",
      "颜色不均匀"
    ]

没有冲突时填写：

`"conflicting_concepts": []`

规则：

1. 典型支持型通常为空；
2. 部分支持型通常为空；
3. 证据不足型通常为空；
4. 鉴别混淆型应至少包含 1 个冲突概念；
5. 冲突困难型应至少包含 1 个冲突概念。

---

### 6.14 missing_information

含义：

当前病例未提供，但会影响临床判断的重要信息。

类型：

字符串数组。

示例：

    "missing_information": [
      "皮肤镜检查结果",
      "组织病理检查结果",
      "患者年龄"
    ]

要求：

1. 至少包含一项；
2. 证据不足型病例应重点记录关键缺失信息；
3. 可以包括年龄、病程、皮肤镜、病理、症状和变化情况。

---

### 6.15 evidence_expectation

含义：

根据病例设计，预期的外部证据支持状态。

类型：

字符串。

允许值：

- `sufficient`
- `partial`
- `insufficient`
- `conflicting`

建议对应关系：

| 病例类型 | evidence_expectation |
|---|---|
| `typical_positive` | `sufficient` |
| `partial_support` | `partial` |
| `evidence_insufficient` | `insufficient` |
| `differential_confusion` | `conflicting` |
| `conflict_difficult` | `conflicting` |

---

### 6.16 data_origin

含义：

病例数据来源类型。

类型：

字符串。

正式测试集统一填写：

`"data_origin": "synthetic_kg_grounded"`

该字段表示：

1. 病例根据知识图谱和医学证据人工或规则构造；
2. 病例不是来自真实患者病历；
3. 病例不包含患者隐私信息；
4. 病例主要用于系统评价。

---

### 6.17 source_basis

含义：

构造病例时所依据的知识图谱三元组编号或证据编号。

类型：

字符串数组。

示例：

    "source_basis": [
      "TRI_025",
      "TRI_026",
      "TRI_030"
    ]

要求：

1. 应尽量使用当前 `triples.csv` 中真实存在的编号；
2. 典型支持型应记录主要支持证据；
3. 鉴别混淆型可以同时记录候选疾病和真实疾病的证据；
4. 不得填写不存在的三元组编号。

---

### 6.18 generation_rule

含义：

病例生成规则版本。

类型：

字符串。

正式测试集统一填写：

`"generation_rule": "task4_case_generation_v2"`

---

## 7. JSON 文件整体结构

正式病例集采用以下结构：

    {
      "dataset_name": "task4_formal_case_dataset_v2",
      "dataset_version": "2.0",
      "description": "用于纯 LLM、普通 RAG 和 KG-RAG 三种方法正式对照实验的皮肤病辅助诊断合成病例集。",
      "disease_count": 7,
      "case_type_count": 5,
      "cases_per_disease": 20,
      "total_case_count": 140,
      "data_origin": "synthetic_kg_grounded",
      "cases": []
    }

所有具体病例均写入 `cases` 数组。

---

## 8. 单条病例示例

    {
      "case_id": "CASE_BCC_TP_001",
      "true_label": "基底细胞癌",
      "candidate_disease": "基底细胞癌",
      "observation_text": "患者面部出现光亮的珍珠样结节，表面可见细小血管，近半年缓慢增大。",
      "lesion_features": [
        "珍珠样结节",
        "表面毛细血管扩张",
        "缓慢生长"
      ],
      "anatomical_site": "面部",
      "symptoms": [],
      "duration_change": "近半年缓慢增大",
      "difficulty_level": "easy",
      "case_type": "typical_positive",
      "expected_concepts": [
        "珍珠样结节",
        "表面毛细血管扩张",
        "面部",
        "缓慢生长"
      ],
      "supporting_concepts": [
        "珍珠样结节",
        "表面毛细血管扩张",
        "面部",
        "缓慢生长"
      ],
      "conflicting_concepts": [],
      "missing_information": [
        "皮肤镜检查结果",
        "组织病理检查结果"
      ],
      "evidence_expectation": "sufficient",
      "data_origin": "synthetic_kg_grounded",
      "source_basis": [
        "TRI_025",
        "TRI_026",
        "TRI_030"
      ],
      "generation_rule": "task4_case_generation_v2"
    }

---

## 9. 不同病例类型的字段约束

| 病例类型 | candidate_disease 与 true_label | supporting_concepts | conflicting_concepts | evidence_expectation |
|---|---|---|---|---|
| `typical_positive` | 一致 | 至少 3 个 | 通常为空 | `sufficient` |
| `partial_support` | 一致 | 1 至 2 个 | 通常为空 | `partial` |
| `evidence_insufficient` | 一般一致 | 0 至 1 个 | 通常为空 | `insufficient` |
| `differential_confusion` | 可以不同 | 至少 1 个 | 至少 1 个 | `conflicting` |
| `conflict_difficult` | 可以不同 | 至少 1 个 | 至少 1 个 | `conflicting` |

---

## 10. 模型输入字段

运行纯 LLM、普通 RAG 和 KG-RAG 时，只允许向模型提供以下字段：

- `case_id`
- `candidate_disease`
- `observation_text`

不得向模型提供以下评价字段：

- `true_label`
- `case_type`
- `difficulty_level`
- `expected_concepts`
- `supporting_concepts`
- `conflicting_concepts`
- `missing_information`
- `evidence_expectation`
- `source_basis`

这些字段只用于实验评价和结果分析。

---

## 11. 正式测试集验收条件

正式测试集必须同时满足以下条件：

1. 病例总数等于 140；
2. 疾病类别总数等于 7；
3. 每类疾病包含 20 条病例；
4. 每类疾病的 5 种病例类型各包含 4 条；
5. 所有 `case_id` 均唯一；
6. 所有病例均包含规定字段；
7. 所有疾病标签均使用标准名称；
8. `observation_text` 不得为空；
9. `lesion_features` 不得为空；
10. `expected_concepts` 不得为空；
11. `missing_information` 不得为空；
12. 鉴别混淆型必须包含冲突概念；
13. 冲突困难型必须包含冲突概念；
14. 典型支持型至少包含 3 个支持概念；
15. 所有 `source_basis` 编号必须在知识图谱数据中存在；
16. 不得包含真实患者姓名、联系方式、地址或其他隐私信息；
17. 测试集必须通过自动验证脚本；
18. 正式实验开始前必须记录文件 SHA256；
19. 正式实验开始后不得直接修改病例内容；
20. 如需修改病例，必须建立新的数据集版本。

---

## 12. 正式实验使用规则

1. 三种方法必须使用同一个病例文件；
2. 三种方法必须使用完全相同的 `candidate_disease`；
3. 三种方法必须使用完全相同的 `observation_text`；
4. 三种方法必须使用同一个大语言模型；
5. 三种方法必须使用相同的温度、最大输出 Token 和 Prompt 输出格式；
6. 纯 LLM 不允许使用外部检索证据；
7. 普通 RAG 只允许使用普通文本检索结果；
8. KG-RAG 只允许使用图谱检索和排序后的证据路径；
9. 正式结果必须记录模型名称、Prompt 版本、Token 和响应时间；
10. 正式结果必须支持断点续跑和失败重试；
11. 正式实验结果不得与 7 条冒烟测试结果混合存放；
12. 正式实验过程中不得修改病例集或知识图谱；
13. 如修改知识图谱或检索配置，必须建立新的实验版本。

---

## 13. 文件命名规范

| 文件用途 | 文件路径 |
|---|---|
| 7 条冒烟测试集 | `experiments/cases/task4_cases_v1.json` |
| 140 条正式测试集 | `experiments/cases/task4_cases_v2.json` |
| 正式病例规范 | `docs/experiments/task4_case_spec_v2.md` |
| 正式病例验证脚本 | `experiments/validate_task4_cases_v2.py` |
| 正式批量实验结果 | `experiments/results/task4_batch_v2/` |
| 正式指标结果 | `experiments/results/task4_metrics_v2/` |

---

## 14. 当前版本说明

当前版本：

`V2.0`

当前阶段目标：

1. 按照本规范构建 140 条正式病例；
2. 编写病例集自动验证脚本；
3. 验证疾病数量、病例类型和字段完整性；
4. 冻结正式病例集版本及 SHA256；
5. 在病例集冻结后开展三种方法的正式批量实验。