export interface KgStatus {
  entity_count: number
  triple_count: number
  source_count: number
  disease_count: number
  csv_dir: string
  csv_available: boolean
  loaded: boolean
  warnings: string[]
}

export interface Disease {
  entity_id: string
  name_cn: string
  name_en: string
  ham10000_label: string
}

export interface EntityRef {
  entity_id: string
  name_cn: string
  name_en: string
  entity_type?: string
}

export interface RelationRef {
  relation_cn: string
  relation_en: string
}

export interface EvidenceItem {
  triple_id: string
  head: EntityRef
  relation: RelationRef
  tail: EntityRef
  evidence_text: string
  source_id: string
  source_name: string
  source_type: string
  note: string
}

export interface FeatureDiseaseMatch {
  disease: Disease
  evidence: EvidenceItem
}

export interface EvidenceContext {
  structured_context: Record<string, unknown>
  markdown_context: string
  evidence_sections: Record<string, EvidenceItem[]>
  sources: Array<Record<string, string>>
  kg_status: KgStatus
}

export interface PromptResult {
  prompt_text: string
  candidate_disease: string
  evidence_summary: Record<string, unknown>
  prompt_version: string
  safety_constraints: string[]
}

export interface TemplateGeneration {
  candidate_disease: string
  observation_evidence_matches: Array<Record<string, string>>
  supporting_evidence: Array<Record<string, string>>
  differential_diagnosis: Array<Record<string, string>>
  risk_warnings: Array<Record<string, string>>
  medical_advice_or_exams: Array<Record<string, string>>
  insufficient_evidence: string[]
  disclaimer: string
  generation_mode: 'template'
}

