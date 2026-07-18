<template>
  <MainLayout>
    <section class="page-section">
      <div class="section-title">
        <div>
          <h3>KG-RAG 辅助解释</h3>
          <p class="muted">医生端演示页面，可查看完整 Prompt；真实大模型调用、候选排序评分和自动一致性校验暂未接入。</p>
        </div>
        <el-tag type="warning" effect="plain">模板降级生成</el-tag>
      </div>

      <ErrorState :message="error" />

      <el-form label-position="top">
        <el-form-item label="观察信息或皮损特征">
          <el-input
            v-model="observation"
            type="textarea"
            :rows="4"
            maxlength="500"
            show-word-limit
            placeholder="例如：患者皮损表现为珍珠样结节，表面可见血管，位于面部。"
          />
        </el-form-item>
        <div class="action-row">
          <el-button type="success" :loading="lookupLoading" @click="lookupByObservation">
            根据观察反查候选疾病
          </el-button>
          <el-select v-model="selectedDiseaseId" filterable placeholder="或直接选择候选疾病" class="disease-select">
            <el-option
              v-for="disease in diseases"
              :key="disease.entity_id"
              :label="diseaseLabel(disease)"
              :value="disease.entity_id"
            />
          </el-select>
          <el-button type="primary" :loading="analysisLoading" @click="runAssistant">
            生成结构化辅助解释
          </el-button>
        </div>
      </el-form>
    </section>

    <section v-if="candidateMatches.length" class="page-section">
      <div class="section-title">
        <h3>反查到的候选疾病</h3>
        <el-tag type="info">请选择后生成解释</el-tag>
      </div>
      <div class="grid grid-2">
        <el-card v-for="match in candidateMatches" :key="match.evidence.triple_id" shadow="never">
          <h4>{{ match.disease.name_cn }}</h4>
          <p class="muted">{{ match.disease.name_en }} / {{ match.disease.ham10000_label }}</p>
          <p>{{ match.evidence.evidence_text }}</p>
          <el-button type="primary" @click="selectedDiseaseId = match.disease.entity_id">选择该候选疾病</el-button>
        </el-card>
      </div>
    </section>

    <section v-if="evidenceItems.length" class="page-section">
      <div class="section-title">
        <h3>图谱证据链</h3>
        <el-tag type="warning" effect="plain">证据来源必须追溯</el-tag>
      </div>
      <EvidenceCard v-for="item in evidenceItems" :key="item.triple_id" :evidence="item" />
    </section>

    <section v-if="generation" class="page-section">
      <div class="section-title">
        <h3>结构化辅助解释</h3>
        <el-tag type="success">generation_mode={{ generation.generation_mode }}</el-tag>
      </div>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="候选疾病">{{ selectedDisease?.name_cn || generation.candidate_disease }}</el-descriptions-item>
        <el-descriptions-item label="免责声明">{{ generation.disclaimer }}</el-descriptions-item>
      </el-descriptions>

      <div class="result-grid">
        <ResultList title="用户观察与证据匹配" :items="generation.observation_evidence_matches" empty-text="给定证据不足：观察信息未形成明确匹配。" />
        <ResultList title="支持证据" :items="generation.supporting_evidence" />
        <ResultList title="鉴别诊断" :items="generation.differential_diagnosis" />
        <ResultList title="风险提示" :items="generation.risk_warnings" />
        <ResultList title="就医/检查建议" :items="generation.medical_advice_or_exams" />
      </div>

      <el-alert class="page-section" type="info" :closable="false" title="证据不足说明">
        <ul>
          <li v-for="item in generation.insufficient_evidence" :key="item">{{ item }}</li>
        </ul>
      </el-alert>
    </section>

    <section v-if="prompt" class="page-section">
      <el-collapse>
        <el-collapse-item title="查看医生端完整 Prompt（患者端不展示）" name="prompt">
          <pre class="prompt-box">{{ prompt.prompt_text }}</pre>
        </el-collapse-item>
      </el-collapse>
    </section>
  </MainLayout>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getDiseaseEvidence, getDiseases, reverseLookupByFeature } from '@/api/kg'
import { buildPrompt, generateTemplateExplanation } from '@/api/kgRag'
import ErrorState from '@/components/ErrorState.vue'
import EvidenceCard from '@/components/EvidenceCard.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import type { Disease, EvidenceItem, FeatureDiseaseMatch, PromptResult, TemplateGeneration } from '@/types/kg'
import { diseaseLabel } from '@/utils/formatters'

const ResultList = defineComponent({
  props: {
    title: { type: String, required: true },
    items: { type: Array as () => Array<Record<string, string>>, required: true },
    emptyText: { type: String, default: '给定证据不足。' }
  },
  setup(props) {
    return () =>
      h('section', { class: 'result-box' }, [
        h('h4', props.title),
        props.items.length
          ? h(
              'ul',
              props.items.map((item) =>
                h('li', { key: `${item.evidence_path}-${item.evidence_text}` }, [
                  h('strong', item.evidence_path || '证据路径未标注'),
                  h('p', item.evidence_text || ''),
                  h('p', { class: 'muted' }, item.source || '')
                ])
              )
            )
          : h('p', props.emptyText)
      ])
  }
})

const route = useRoute()
const error = ref('')
const lookupLoading = ref(false)
const analysisLoading = ref(false)
const diseases = ref<Disease[]>([])
const selectedDiseaseId = ref('')
const observation = ref('患者皮损表现为珍珠样结节，表面可见血管，位于面部。')
const candidateMatches = ref<FeatureDiseaseMatch[]>([])
const evidenceItems = ref<EvidenceItem[]>([])
const prompt = ref<PromptResult | null>(null)
const generation = ref<TemplateGeneration | null>(null)

const selectedDisease = computed(() => diseases.value.find((item) => item.entity_id === selectedDiseaseId.value))

async function loadBaseData() {
  try {
    diseases.value = await getDiseases()
    const queryDisease = typeof route.query.disease === 'string' ? route.query.disease : ''
    const queryObservation = typeof route.query.observation === 'string' ? route.query.observation : ''
    if (queryDisease) selectedDiseaseId.value = queryDisease
    if (queryObservation) observation.value = queryObservation
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取疾病列表失败'
  }
}

async function lookupByObservation() {
  if (!observation.value.trim()) {
    error.value = '请先填写观察信息或皮损特征'
    return
  }
  lookupLoading.value = true
  error.value = ''
  try {
    candidateMatches.value = await reverseLookupByFeature(observation.value.trim())
    if (candidateMatches.value[0]) {
      selectedDiseaseId.value = candidateMatches.value[0].disease.entity_id
    }
  } catch (err) {
    candidateMatches.value = []
    error.value = '未能通过观察信息直接反查候选疾病，可从疾病列表中选择；该选择仅用于健康信息查询，不代表诊断结果。'
  } finally {
    lookupLoading.value = false
  }
}

async function runAssistant() {
  if (!selectedDiseaseId.value) {
    error.value = '请先选择候选疾病'
    return
  }
  if (!observation.value.trim()) {
    error.value = '请先填写观察信息'
    return
  }
  analysisLoading.value = true
  error.value = ''
  prompt.value = null
  generation.value = null
  evidenceItems.value = []
  try {
    const disease = selectedDisease.value
    const diseaseQuery = disease?.entity_id || selectedDiseaseId.value
    const [evidence, promptResult, generationResult] = await Promise.all([
      getDiseaseEvidence(diseaseQuery),
      buildPrompt(diseaseQuery, observation.value.trim()),
      generateTemplateExplanation(diseaseQuery, observation.value.trim())
    ])
    evidenceItems.value = evidence
    prompt.value = promptResult
    generation.value = generationResult
  } catch (err) {
    error.value = err instanceof Error ? err.message : '生成辅助解释失败'
  } finally {
    analysisLoading.value = false
  }
}

onMounted(loadBaseData)
</script>

<style scoped>
.disease-select {
  min-width: 320px;
}

.result-grid {
  display: grid;
  gap: 14px;
  margin-top: 16px;
}

.result-box h4 {
  margin: 0 0 8px;
}

.result-box ul {
  padding-left: 18px;
}

.result-box li + li {
  margin-top: 10px;
}
</style>

