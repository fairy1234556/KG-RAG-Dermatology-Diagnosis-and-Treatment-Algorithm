# V1.0 API 清单设计

## 1. API 设计原则

V1.0 API 采用前后端分离设计，建议以 FastAPI 提供 REST 接口。接口统一返回请求标识、状态、数据和可读错误信息。

统一响应格式建议：

```json
{
  "request_id": "req_xxx",
  "success": true,
  "message": "ok",
  "data": {}
}
```

医学分析相关接口必须返回：

- 图谱版本。
- Prompt 版本。
- 模型版本或模板模式。
- 算法版本。
- 证据来源标识。
- 非诊断和非概率说明。

角色边界：

- `researcher` 仅访问实验、评价、版本和脱敏研究材料。
- `researcher` 不访问未经授权的患者病例、医生审核详情或可识别个人信息。
- 患者不能直接获得医生端完整候选评分和专业指标，只能通过患者解释接口获得裁剪后的结果。

本文件仅列接口设计，不实现。

## 2. 认证与用户

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `POST` | `/api/auth/login` | 全部 | 登录 |
| `POST` | `/api/auth/logout` | 已登录 | 退出 |
| `GET` | `/api/auth/me` | 已登录 | 获取当前用户 |
| `GET` | `/api/auth/permissions` | 已登录 | 获取角色权限 |
| `POST` | `/api/auth/disclaimer-confirmations` | 全部 | 记录免责声明确认 |
| `GET` | `/api/users` | 系统管理员 | 用户列表 |
| `POST` | `/api/users` | 系统管理员 | 创建演示或系统用户 |
| `PATCH` | `/api/users/{user_id}` | 系统管理员 | 更新用户状态 |
| `GET` | `/api/roles` | 系统管理员 | 角色列表 |

## 3. 病例

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `GET` | `/api/cases` | 医生、患者、系统管理员 | 查询病例列表，按角色控制范围 |
| `POST` | `/api/cases` | 医生、患者 | 创建病例 |
| `GET` | `/api/cases/{case_id}` | 有权限用户 | 查看病例详情 |
| `PATCH` | `/api/cases/{case_id}` | 医生、患者本人 | 更新病例草稿 |
| `POST` | `/api/cases/{case_id}/archive` | 医生、患者本人、系统管理员 | 归档病例 |
| `GET` | `/api/cases/{case_id}/timeline` | 医生、系统管理员 | 病例时间线 |
| `POST` | `/api/cases/{case_id}/observations` | 医生、患者本人 | 保存临床观察 |
| `GET` | `/api/cases/{case_id}/observations` | 有权限用户 | 查看临床观察 |
| `PATCH` | `/api/observations/{observation_id}` | 医生、患者本人 | 更新观察 |

## 4. 图片

V1.0 图片仅用于病例资料关联，不返回自动分类结论。

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `POST` | `/api/cases/{case_id}/images` | 医生、患者本人 | 上传 JPG/JPEG/PNG 图片 |
| `GET` | `/api/cases/{case_id}/images` | 有权限用户 | 获取病例图片列表 |
| `GET` | `/api/images/{image_id}` | 有权限用户 | 获取图片预览 |
| `PATCH` | `/api/images/{image_id}` | 上传人、医生 | 更新图片说明 |
| `DELETE` | `/api/images/{image_id}` | 上传人、医生 | 逻辑删除图片 |

## 5. 图谱

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `GET` | `/api/kg/status` | 全部已登录 | 当前图谱状态和版本 |
| `GET` | `/api/kg/entities` | 医生、知识管理员、系统管理员 | 实体搜索 |
| `GET` | `/api/kg/entities/{entity_id}` | 医生、知识管理员、系统管理员 | 实体详情 |
| `GET` | `/api/kg/diseases` | 全部已登录 | 七类疾病列表 |
| `GET` | `/api/kg/diseases/{disease_id}/evidence` | 医生、知识管理员、系统管理员 | 疾病证据列表 |
| `GET` | `/api/kg/diseases/{disease_id}/relations/{relation_en}` | 医生、知识管理员、系统管理员 | 按关系查询疾病证据 |
| `GET` | `/api/kg/features/{feature_id}/diseases` | 医生、系统管理员 | 特征反查疾病 |
| `GET` | `/api/kg/paths` | 医生、系统管理员 | 证据路径检索 |
| `GET` | `/api/kg/subgraph` | 医生、知识管理员、系统管理员 | 疾病子图 |
| `GET` | `/api/kg/sources` | 知识管理员、系统管理员 | 来源列表 |
| `GET` | `/api/kg/sources/{source_id}` | 知识管理员、系统管理员 | 来源详情 |
| `POST` | `/api/kg/quality-checks` | 知识管理员、系统管理员 | CSV 重复、悬空节点、来源缺失检查 |

## 6. 分析

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `POST` | `/api/cases/{case_id}/semantic-anchors` | 医生、患者本人 | 识别语义锚点 |
| `GET` | `/api/cases/{case_id}/semantic-anchors` | 有权限用户 | 查询语义锚点 |
| `PATCH` | `/api/semantic-anchors/{anchor_id}` | 医生 | 医生修正标准化结果 |
| `POST` | `/api/cases/{case_id}/analysis-runs` | 医生 | 完整分析编排：语义锚点识别、候选排序、证据召回、KG-RAG 或模板生成、声明校验、报告草稿 |
| `POST` | `/api/cases/{case_id}/analysis/candidates` | 医生、系统管理员、研究人员 `researcher` | 候选疾病排序，供调试和实验使用 |
| `GET` | `/api/analysis-tasks/{task_id}` | 有权限用户 | 查询分析任务状态 |
| `GET` | `/api/cases/{case_id}/candidates` | 医生、系统管理员 | 查询医生端候选疾病和分项评分 |
| `POST` | `/api/cases/{case_id}/analysis/specified-disease` | 医生 | 指定疾病解释分析 |

完整分析编排接口负责：语义锚点识别 -> 候选排序 -> 证据召回 -> KG-RAG 或模板生成 -> 声明校验 -> 报告草稿。细分接口保留给调试、实验和后台研究使用。

候选排序响应必须包含：

- `total_score`
- `feature_score`
- `site_score`
- `symptom_score`
- `evidence_coverage_score`
- `conflict_penalty`
- `score_note`: 明确综合分不是患病概率。

评分约束：

- 公式为 `Score(d) = αMf + βMl + γMs + ηCe - λCf`。
- 风险提示不参与候选疾病排序，只在候选疾病形成后单独生成。
- 未填写、未知、未观察不能作为冲突惩罚。
- 只有用户明确描述且与图谱证据矛盾时，才计入 `conflict_penalty`。

## 7. KG-RAG

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `POST` | `/api/kg-rag/evidence-context` | 医生、系统管理员 | 构造证据上下文 |
| `POST` | `/api/kg-rag/prompts` | 医生、系统管理员 | 构造 KG-RAG Prompt |
| `POST` | `/api/kg-rag/generations` | 医生、系统管理员 | 生成医生端辅助解释 |
| `POST` | `/api/kg-rag/patient-explanations` | 患者本人、医生 | 生成患者端裁剪后的通俗解释 |
| `POST` | `/api/kg-rag/template-generations` | 医生、患者本人、系统管理员 | 模板降级生成 |
| `GET` | `/api/kg-rag/generations/{generation_id}` | 有权限用户 | 查询生成结果 |

生成接口必须约束：

- 不替代医生诊断。
- 不输出处方、药物剂量。
- 证据不足时明确说明。
- 患者端不展示医生端完整候选评分或专业实验指标。
- 患者端就医建议固定使用“需常规关注”“建议预约皮肤科评估”“建议尽快就医评估”。

## 8. 证据一致性校验

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `POST` | `/api/validation/claims` | 医生、系统管理员 | 拆分医学声明 |
| `POST` | `/api/validation/evidence-match` | 医生、系统管理员 | 声明与图谱证据匹配 |
| `POST` | `/api/reports/{report_id}/validate` | 医生、系统管理员 | 校验报告 |
| `GET` | `/api/reports/{report_id}/claims` | 医生、系统管理员 | 查询报告声明 |
| `GET` | `/api/reports/{report_id}/validation-results` | 医生、系统管理员 | 查询声明校验结果 |
| `GET` | `/api/reports/{report_id}/validation-metrics` | 医生、系统管理员 | 查询报告级指标 |

校验状态：

- `supported`
- `partially_supported`
- `unsupported`
- `not_verifiable`

无法判断的声明不得自动记为支持。

指标定义：

- `OEHR = 命中图谱证据的有效观察锚点数 / 可标准化的有效观察锚点总数`。
- `UCR = unsupported 声明数 / 可验证医学声明总数`；`not_verifiable` 不得自动算作 `supported`，单独记录。
- `PCS = 疾病、关系和尾实体均与图谱路径一致的声明数 / 成功映射为结构化路径的声明总数`。
- `ECR = 输出实际使用的相关证据类型数 / 当前任务可用的相关证据类型数`。

## 9. 医生审核

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `GET` | `/api/reviews/pending` | 医生 | 待审核病例列表 |
| `POST` | `/api/reports/{report_id}/reviews` | 医生 | 创建医生审核草稿 |
| `GET` | `/api/cases/{case_id}/reviews` | 医生、系统管理员 | 查看审核历史 |
| `PATCH` | `/api/reviews/{review_id}` | 医生 | 修改未最终提交的审核 |
| `POST` | `/api/reviews/{review_id}/submit` | 医生 | 最终提交审核 |
| `POST` | `/api/reports/{report_id}/candidate-adjustments` | 医生 | 调整候选排序或删除不适用内容 |
| `POST` | `/api/feedback` | 医生、患者 | 提交反馈 |

审核接口要求：

- 保存系统原始输出。
- 保存医生修订版本。
- 审核记录包含 `status=draft/submitted` 和 `decision=approved/revised/rejected/needs_followup`。
- `submitted_at` 仅最终提交时填写。
- 更新病例状态为 `reviewed`。
- 写入操作日志。

## 10. 报告

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `POST` | `/api/cases/{case_id}/reports` | 医生、系统管理员 | 创建报告草稿 |
| `GET` | `/api/cases/{case_id}/reports` | 有权限用户 | 查看病例报告列表 |
| `GET` | `/api/reports/{report_id}` | 有权限用户 | 查看报告详情 |
| `POST` | `/api/reports/{report_id}/versions` | 医生 | 保存新版本 |
| `GET` | `/api/reports/{report_id}/versions` | 有权限用户 | 查看版本列表 |
| `POST` | `/api/reports/{report_id}/export` | 医生 | 导出报告 |
| `GET` | `/api/reports/{report_id}/print-view` | 医生 | 打印视图 |

报告必须包含：

- 病例摘要。
- 候选疾病。
- 证据链。
- 鉴别诊断。
- 风险/检查提示。
- 校验结果。
- 医生意见。
- 版本信息。
- 免责声明。

报告版本要求：

- 同一报告族使用 `report_group_no` 串联。
- 新版本使用 `parent_report_id` 指向上一版或系统原始版本。
- 当前展示版本使用 `is_current` 标记。
- 唯一约束为 `UNIQUE(case_id, report_group_no, version_no)`。
- 系统原始版本和医生修订版本分开保存，不得覆盖系统原始报告。

## 11. 实验

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `GET` | `/api/experiments/runs` | 系统管理员、研究人员 `researcher` | 实验列表 |
| `POST` | `/api/experiments/runs` | 系统管理员、研究人员 `researcher` | 创建实验记录 |
| `POST` | `/api/experiments/import-existing` | 系统管理员、研究人员 `researcher` | 导入现有 `work`、`outputs`、`experiments` 结果 |
| `GET` | `/api/experiments/runs/{run_id}` | 系统管理员、研究人员 `researcher` | 实验详情 |
| `GET` | `/api/experiments/runs/{run_id}/cases` | 系统管理员、研究人员 `researcher` | 实验样例结果 |
| `GET` | `/api/experiments/runs/{run_id}/metrics` | 系统管理员、研究人员 `researcher` | 指标汇总 |
| `GET` | `/api/experiments/cases/{case_result_id}` | 系统管理员、研究人员 `researcher` | 单样例输出详情 |
| `POST` | `/api/experiments/runs/{run_id}/export` | 系统管理员、研究人员 `researcher` | 导出实验结果 |

## 12. 后台管理

### 12.1 版本管理

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `GET` | `/api/admin/kg-versions` | 知识管理员、系统管理员 | 图谱版本列表 |
| `POST` | `/api/admin/kg-versions` | 知识管理员、系统管理员 | 创建图谱版本记录 |
| `POST` | `/api/admin/kg-versions/{version_id}/activate` | 系统管理员 | 启用图谱版本 |
| `GET` | `/api/admin/prompt-versions` | 系统管理员 | Prompt 版本列表 |
| `POST` | `/api/admin/prompt-versions` | 系统管理员 | 创建 Prompt 版本 |
| `POST` | `/api/admin/prompt-versions/{version_id}/activate` | 系统管理员 | 启用 Prompt 版本 |
| `GET` | `/api/admin/model-versions` | 系统管理员 | 模型版本列表 |
| `POST` | `/api/admin/model-versions` | 系统管理员 | 创建模型配置 |
| `GET` | `/api/admin/algorithm-versions` | 系统管理员 | 算法版本列表 |
| `POST` | `/api/admin/algorithm-versions` | 系统管理员 | 创建算法版本 |

### 12.2 系统配置与日志

| 方法 | 路径 | 角色 | 用途 |
|---|---|---|---|
| `GET` | `/api/admin/settings` | 系统管理员 | 查询系统设置 |
| `PATCH` | `/api/admin/settings` | 系统管理员 | 更新非敏感设置 |
| `GET` | `/api/admin/health` | 系统管理员 | 系统健康检查 |
| `GET` | `/api/admin/logs` | 系统管理员 | 操作日志查询 |
| `GET` | `/api/admin/logs/{log_id}` | 系统管理员 | 操作日志详情 |

## 13. 错误码建议

| 错误码 | 含义 |
|---|---|
| `AUTH_INVALID_CREDENTIALS` | 登录失败 |
| `AUTH_FORBIDDEN` | 权限不足 |
| `CASE_NOT_FOUND` | 病例不存在 |
| `CASE_ACCESS_DENIED` | 无病例访问权限 |
| `KG_ENTITY_NOT_FOUND` | 图谱实体不存在 |
| `KG_EVIDENCE_NOT_FOUND` | 未找到图谱证据 |
| `ANALYSIS_INSUFFICIENT_INPUT` | 输入信息不足 |
| `ANALYSIS_OUT_OF_SCOPE` | 超出 HAM10000 七类范围 |
| `MODEL_UNAVAILABLE` | 模型不可用，建议模板降级 |
| `VALIDATION_NOT_VERIFIABLE` | 声明无法校验 |
| `FILE_TYPE_NOT_ALLOWED` | 文件类型不允许 |
| `FILE_TOO_LARGE` | 文件过大 |

## 14. V1.0 不提供的接口

- 自动皮肤镜图片分类接口。
- Grad-CAM 可视化接口。
- 处方生成接口。
- 药物剂量推荐接口。
- 替代医生确认最终诊断的接口。
- 面向全皮肤病范围的泛化诊断接口。
