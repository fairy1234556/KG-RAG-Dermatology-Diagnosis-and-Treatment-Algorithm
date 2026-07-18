import { http, requestData } from '@/api/http'
import type { EvidenceContext, PromptResult, TemplateGeneration } from '@/types/kg'

export function buildEvidenceContext(candidateDisease: string) {
  return requestData<EvidenceContext>(
    http.post('/kg-rag/evidence-context', {
      candidate_disease: candidateDisease
    })
  )
}

export function buildPrompt(candidateDisease: string, userObservation: string, promptVersion = 'doctor_kg_rag_v1') {
  return requestData<PromptResult>(
    http.post('/kg-rag/prompts', {
      candidate_disease: candidateDisease,
      user_observation: userObservation,
      prompt_version: promptVersion
    })
  )
}

export function generateTemplateExplanation(candidateDisease: string, userObservation: string) {
  return requestData<TemplateGeneration>(
    http.post('/kg-rag/template-generations', {
      candidate_disease: candidateDisease,
      user_observation: userObservation
    })
  )
}

