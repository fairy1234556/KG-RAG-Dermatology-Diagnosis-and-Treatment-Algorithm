# KG-RAG Case 002：黑色素瘤

## 输入信息

候选疾病：黑色素瘤

用户观察：患者皮损表现为形态不对称，边界不规则，颜色不均。

## KG-RAG 输出结果

候选疾病：

* 中文名称：黑色素瘤
* 英文名称：Melanoma
* 疾病 ID：DIS_001
* 结论表述：根据给定知识图谱证据，用户观察到的“形态不对称”“边界不规则”和“颜色不均”均与黑色素瘤的相关皮损表现存在对应关系，因此该候选疾病具有一定证据支持。但该结果仅为基于知识图谱证据的辅助解释，不能作为确诊结论，仍需结合皮肤镜检查、组织病理检查及医生临床判断进一步评估。

用户观察与证据匹配：

* 观察 1：形态不对称

  * 匹配情况：可能支持黑色素瘤。给定证据显示，ABCDE 特征中的 Asymmetry 可支持“形态不对称”。
  * 对应证据路径：黑色素瘤 — 表现为 — 形态不对称
  * evidence_text：ABCDE 特征包括 Asymmetry，可支持“形态不对称”。
  * source：DermNet - ABCDEFG of melanoma (SRC_001, Website)

* 观察 2：边界不规则

  * 匹配情况：可能支持黑色素瘤。给定证据显示，ABCDE 特征中的 Border irregularity 可支持“边界不规则”。
  * 对应证据路径：黑色素瘤 — 表现为 — 边界不规则
  * evidence_text：ABCDE 特征包括 Border irregularity，可支持“边界不规则”。
  * source：DermNet - ABCDEFG of melanoma (SRC_001, Website)

* 观察 3：颜色不均

  * 匹配情况：可能支持黑色素瘤。给定证据显示，ABCDE 特征中的 Colour variability / Change 可支持“颜色不均”。
  * 对应证据路径：黑色素瘤 — 表现为 — 颜色不均
  * evidence_text：ABCDE 特征包括 Colour variability / Change，可支持“颜色不均”。
  * source：DermNet - ABCDEFG of melanoma (SRC_001, Website)

支持证据：
1.

* 证据路径：黑色素瘤 — 表现为 — 形态不对称
* evidence_text：ABCDE 特征包括 Asymmetry，可支持“形态不对称”。
* source：DermNet - ABCDEFG of melanoma (SRC_001, Website)

2. - 证据路径：黑色素瘤 — 表现为 — 边界不规则
   - evidence_text：ABCDE 特征包括 Border irregularity，可支持“边界不规则”。
   - source：DermNet - ABCDEFG of melanoma (SRC_001, Website)

3. * 证据路径：黑色素瘤 — 表现为 — 颜色不均
   * evidence_text：ABCDE 特征包括 Colour variability / Change，可支持“颜色不均”。
   * source：DermNet - ABCDEFG of melanoma (SRC_001, Website)

鉴别诊断：

* 需要鉴别的疾病或病变：黑色素细胞痣
* 对应证据路径：黑色素瘤 — 鉴别诊断 — 黑色素细胞痣
* evidence_text：黑色素瘤早期可能类似黑色素细胞痣，部分情况下很难与非典型痣区分。
* source：DermNet - Atypical naevi / Superficial spreading melanoma (SRC_005, Website)

风险提示：

* 风险说明：给定证据提示黑色素瘤属于潜在严重的皮肤癌，存在恶性风险，需要进一步医学评估。
* 对应证据路径：黑色素瘤 — 风险提示 — 存在恶性风险，需进一步评估
* evidence_text：黑色素瘤是潜在严重的皮肤癌，需进行进一步评估。
* source：DermNet - Melanoma (SRC_002, Website)

就医建议：

* 建议内容：建议皮肤科就诊，必要时进行皮肤镜检查或病理活检，以进一步明确诊断。该建议仅为就医方向提示，不涉及具体治疗方案或用药建议。
* 对应证据路径：黑色素瘤 — 建议检查 — 皮肤镜检查；黑色素瘤 — 建议检查 — 组织病理检查；黑色素瘤 — 就医建议 — 建议皮肤科就诊，必要时行病理活检
* evidence_text：皮肤镜可用于黑色素瘤相关皮损评估。活检可提供组织病理信息，用于优化黑色素瘤诊断并指导后续管理。疑似黑色素瘤时，活检获得的组织病理信息有助于诊断和后续管理。
* source：DermNet - Dermoscopy / Melanoma (SRC_004, Website)；AAD - Melanoma clinical guideline (SRC_003, Guideline)

证据不足说明：

* 给定证据不足的内容：当前证据不能直接确认该患者已经患有黑色素瘤，也不能判断病变分期、严重程度、转移风险或具体治疗方案。
* 原因说明：给定知识图谱证据仅提供皮损表现、常见部位、伴随症状、建议检查、鉴别诊断、风险提示和就医建议等信息；缺少患者皮肤镜图像、病理结果、病程变化、既往史、家族史和医生体格检查信息，因此只能形成辅助解释，不能替代临床诊断。
