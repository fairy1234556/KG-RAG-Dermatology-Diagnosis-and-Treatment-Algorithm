# KG-RAG Case 003：黑色素细胞痣

## 输入信息

候选疾病：黑色素细胞痣

用户观察：患者皮损表现为色素性斑片，整体较对称，边界相对规则。

## KG-RAG 输出结果

候选疾病：

* 中文名称：黑色素细胞痣
* 英文名称：Melanocytic Nevus
* 疾病 ID：DIS_002
* 结论表述：根据给定知识图谱证据，用户观察到的“色素性斑片”“整体较对称”和“边界相对规则”与黑色素细胞痣的部分良性色素性皮损表现存在对应关系，因此该候选疾病具有一定证据支持。但该结果仅为基于知识图谱证据的辅助解释，不能作为确诊结论，仍需结合皮肤镜检查及医生临床判断进一步评估。

用户观察与证据匹配：

* 观察 1：色素性斑片

  * 匹配情况：可能支持黑色素细胞痣。给定证据显示，棕色或黑色黑色素细胞痣含有黑色素，也可称为色素痣；同时，单一颜色或均匀色素模式的皮损几乎总是良性的。
  * 对应证据路径：黑色素细胞痣 — 表现为 — 棕色或黑色斑疹/丘疹；黑色素细胞痣 — 表现为 — 色素均匀
  * evidence_text：棕色或黑色黑色素细胞痣含有黑色素，也可称为色素痣。单一颜色或均匀色素模式的皮损几乎总是良性的。
  * source：DermNet - Melanocytic Naevus (SRC_006, Website)；DermNet - Benign Melanocytic Lesions (SRC_007, Website)

* 观察 2：整体较对称

  * 匹配情况：可能支持黑色素细胞痣。给定证据显示，良性色素性皮损通常具有较一致的结构和外观，可与“整体较对称”形成对应。
  * 对应证据路径：黑色素细胞痣 — 表现为 — 对称性较好
  * evidence_text：良性色素性皮损通常具有较一致的结构和外观。
  * source：DermNet - Benign Melanocytic Lesions (SRC_007, Website)

* 观察 3：边界相对规则

  * 匹配情况：可能支持黑色素细胞痣。给定证据显示，良性色素性皮损通常表现为较规则、较清楚的边界。
  * 对应证据路径：黑色素细胞痣 — 表现为 — 边界清楚
  * evidence_text：良性色素性皮损通常表现为较规则、较清楚的边界。
  * source：DermNet - Benign Melanocytic Lesions (SRC_007, Website)

支持证据：
1.

* 证据路径：黑色素细胞痣 — 表现为 — 色素均匀
* evidence_text：单一颜色或均匀色素模式的皮损几乎总是良性的。
* source：DermNet - Benign Melanocytic Lesions (SRC_007, Website)

2. - 证据路径：黑色素细胞痣 — 表现为 — 边界清楚
   - evidence_text：良性色素性皮损通常表现为较规则、较清楚的边界。
   - source：DermNet - Benign Melanocytic Lesions (SRC_007, Website)

3. * 证据路径：黑色素细胞痣 — 表现为 — 对称性较好
   * evidence_text：良性色素性皮损通常具有较一致的结构和外观。
   * source：DermNet - Benign Melanocytic Lesions (SRC_007, Website)

鉴别诊断：

* 需要鉴别的疾病或病变：黑色素瘤
* 对应证据路径：黑色素细胞痣 — 鉴别诊断 — 黑色素瘤
* evidence_text：皮肤镜可帮助识别与其他痣不同的“丑小鸭”病变，并提示黑色素瘤可能。
* source：DermNet - Melanocytic Naevi: New Classification (SRC_008, Website)

风险提示：

* 风险说明：给定证据提示黑色素细胞痣通常为良性，但如果出现大小、形状、结构、颜色改变，或出现出血、结痂、瘙痒等异常表现，则需要进一步评估。
* 对应证据路径：黑色素细胞痣 — 风险提示 — 通常为良性，形态变化时需警惕
* evidence_text：黑色素细胞痣是一种常见良性皮损。
* source：DermNet - Melanocytic Naevus (SRC_006, Website)

就医建议：

* 建议内容：建议观察皮损变化；如果出现快速增大、颜色改变、出血、结痂或瘙痒等异常表现，应进一步就诊评估。必要时可通过皮肤镜检查辅助判断。该建议仅为就医方向提示，不涉及具体治疗方案或用药建议。
* 对应证据路径：黑色素细胞痣 — 就医建议 — 建议观察皮损变化，出现快速增大、颜色改变或出血时就诊；黑色素细胞痣 — 建议检查 — 皮肤镜检查
* evidence_text：皮损变化、颜色改变或异常表现时应进一步评估。皮肤镜常可根据色素数量和分布对不同类型黑色素细胞痣进行诊断。
* source：DermNet - Melanocytic Naevus (SRC_006, Website)；DermNet - Melanocytic Naevi: New Classification (SRC_008, Website)

证据不足说明：

* 给定证据不足的内容：当前证据不能直接确认该患者皮损一定为黑色素细胞痣，也不能排除黑色素瘤等需鉴别疾病。
* 原因说明：给定知识图谱证据仅提供皮损表现、常见部位、建议检查、鉴别诊断、风险提示和就医建议等信息；缺少患者皮肤镜图像、病程变化、病理结果及医生体格检查信息，因此只能形成辅助解释，不能替代临床诊断。
