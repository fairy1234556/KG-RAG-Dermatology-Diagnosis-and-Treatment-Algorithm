import { describe, expect, it } from 'vitest'

import { MEDICAL_DISCLAIMER, SYSTEM_TITLE } from '@/utils/formatters'

describe('系统中文文案边界', () => {
  it('系统标题为中文', () => {
    expect(SYSTEM_TITLE).toBe('基于知识图谱增强的皮肤病智能辅助诊疗系统')
  })

  it('免责声明不包含处方或药物剂量建议', () => {
    expect(MEDICAL_DISCLAIMER).not.toContain('处方')
    expect(MEDICAL_DISCLAIMER).not.toContain('药物剂量')
  })
})

