import { describe, expect, it } from 'vitest'

import { adviceLevelFromText, diseaseLabel, evidencePath, MEDICAL_DISCLAIMER, sourceLabel } from '@/utils/formatters'
import type { Disease, EvidenceItem } from '@/types/kg'

const disease: Disease = {
  entity_id: 'DIS_003',
  name_cn: '基底细胞癌',
  name_en: 'Basal Cell Carcinoma',
  ham10000_label: 'bcc'
}

const evidence: EvidenceItem = {
  triple_id: 'TRI_025',
  head: { entity_id: 'DIS_003', name_cn: '基底细胞癌', name_en: 'Basal Cell Carcinoma', entity_type: 'Disease' },
  relation: { relation_cn: '表现为', relation_en: 'has_manifestation' },
  tail: { entity_id: 'LF_010', name_cn: '珍珠样结节', name_en: 'Pearly Nodule', entity_type: 'LesionFeature' },
  evidence_text: '结节型基底细胞癌可表现为光亮或珍珠样结节。',
  source_id: 'SRC_009',
  source_name: 'DermNet - Basal Cell Carcinoma',
  source_type: 'Website',
  note: '基底细胞癌皮损特征'
}

describe('中文展示格式化', () => {
  it('优先展示中文疾病名，英文和缩写作为补充', () => {
    expect(diseaseLabel(disease)).toBe('基底细胞癌（Basal Cell Carcinoma / bcc）')
  })

  it('展示证据链路径和医学来源', () => {
    expect(evidencePath(evidence)).toBe('基底细胞癌 → 表现为 → 珍珠样结节')
    expect(sourceLabel(evidence)).toContain('DermNet')
    expect(sourceLabel(evidence)).toContain('SRC_009')
  })

  it('固定显示医学安全免责声明', () => {
    expect(MEDICAL_DISCLAIMER).toContain('不替代医生面诊')
    expect(MEDICAL_DISCLAIMER).toContain('病理诊断')
  })

  it('患者端使用就医引导而不是概率表达', () => {
    expect(adviceLevelFromText('建议皮肤科评估，必要时进一步检查')).toBe('建议预约皮肤科评估')
    expect(adviceLevelFromText('出现反复出血和破溃，需要进一步评估')).toBe('建议尽快就医评估')
    expect(adviceLevelFromText('暂无明显危险信号')).toBe('需常规关注')
  })
})

