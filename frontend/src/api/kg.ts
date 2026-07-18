import { http, requestData } from '@/api/http'
import type { Disease, EvidenceItem, FeatureDiseaseMatch, KgStatus } from '@/types/kg'

export function getHealth() {
  return requestData<{
    service_status: string
    system_version: string
    kg_loaded: boolean
    kg_warnings: string[]
  }>(http.get('/health'))
}

export function getKgStatus() {
  return requestData<KgStatus>(http.get('/kg/status'))
}

export function getDiseases() {
  return requestData<Disease[]>(http.get('/kg/diseases'))
}

export function getDiseaseEvidence(diseaseId: string) {
  return requestData<EvidenceItem[]>(http.get(`/kg/diseases/${encodeURIComponent(diseaseId)}/evidence`))
}

export function reverseLookupByFeature(feature: string) {
  return requestData<FeatureDiseaseMatch[]>(http.get(`/kg/features/${encodeURIComponent(feature)}/diseases`))
}

