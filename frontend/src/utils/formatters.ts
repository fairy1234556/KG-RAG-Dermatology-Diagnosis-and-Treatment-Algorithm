import type { Disease, EvidenceItem } from '@/types/kg'

export const SYSTEM_TITLE = '基于知识图谱增强的皮肤病智能辅助诊疗系统'

export const MEDICAL_DISCLAIMER =
  '本系统结果仅用于辅助决策和健康信息参考，不替代医生面诊、皮肤镜检查及病理诊断。'

export function diseaseLabel(disease?: Disease) {
  if (!disease) return '未选择候选疾病'
  const extras = [disease.name_en, disease.ham10000_label].filter(Boolean).join(' / ')
  return extras ? `${disease.name_cn}（${extras}）` : disease.name_cn
}

export function evidencePath(item: EvidenceItem) {
  return `${item.head.name_cn} → ${item.relation.relation_cn} → ${item.tail.name_cn}`
}

export function sourceLabel(item: EvidenceItem | Record<string, string>) {
  const sourceId = 'source_id' in item ? item.source_id : ''
  const sourceName = 'source_name' in item ? item.source_name : ''
  const sourceType = 'source_type' in item ? item.source_type : ''
  const extras = [sourceId, sourceType].filter(Boolean).join('，')
  return extras ? `${sourceName || '未标注来源'}（${extras}）` : sourceName || '未标注来源'
}

export function adviceLevelFromText(text: string) {
  if (/出血|破溃|快速|恶性|活检|进一步评估|尽快/.test(text)) {
    return '建议尽快就医评估'
  }
  if (/皮肤科|检查|评估|诊断不明确/.test(text)) {
    return '建议预约皮肤科评估'
  }
  return '需常规关注'
}

