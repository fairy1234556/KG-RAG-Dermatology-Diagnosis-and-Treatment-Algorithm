<template>
  <MainLayout>
    <section class="page-section">
      <div class="section-title">
        <div>
          <h3>患者健康咨询</h3>
          <p class="muted">请描述可观察到的皮损表现。系统仅提供健康信息参考和就医引导。</p>
        </div>
        <el-tag type="warning" effect="plain">不显示专业评分</el-tag>
      </div>

      <ErrorState :message="error" />

      <el-form label-position="top">
        <el-form-item label="观察信息或皮损特征">
          <el-input
            v-model="observation"
            type="textarea"
            :rows="4"
            maxlength="400"
            show-word-limit
            placeholder="例如：皮损像珍珠样小结节，表面能看到血管，位置在面部。"
          />
        </el-form-item>
        <div class="action-row">
          <el-button type="primary" :loading="lookupLoading" @click="lookupCandidates">
            先反查相关方向
          </el-button>
          <el-select v-model="selectedDiseaseId" filterable placeholder="选择相关方向" class="disease-select">
            <el-option
              v-for="disease in availableDiseases"
              :key="disease.entity_id"
              :label="disease.name_cn"
              :value="disease.entity_id"
            />
          </el-select>
          <el-button type="success" :loading="explainLoading" @click="generatePatientExplanation">
            生成健康解释
          </el-button>
        </div>
      </el-form>
    </section>

    <section v-if="fallbackMode" class="page-section">
      <el-alert type="warning" :closable="false" title="未能直接反查到相关方向">
        可以从七类疾病范围中选择一个方向进行健康信息查询；该选择仅用于健康信息查询，不代表诊断结果。
      </el-alert>
    </section>

    <section v-if="candidateMatches.length" class="page-section">
      <div class="section-title">
        <h3>反查到的相关方向</h3>
        <el-tag type="warning" effect="plain">不代表诊断结果</el-tag>
      </div>
      <div class="grid grid-2">
        <el-card v-for="match in candidateMatches" :key="match.evidence.triple_id" shadow="never">
          <h4>{{ match.disease.name_cn }}</h4>
          <p>{{ match.evidence.evidence_text }}</p>
          <el-button type="primary" @click="selectedDiseaseId = match.disease.entity_id">选择该方向</el-button>
        </el-card>
      </div>
    </section>

    <section v-if="generation" class="page-section">
      <div class="section-title">
        <h3>健康信息解释</h3>
        <el-tag type="success">{{ careAdvice }}</el-tag>
      </div>

      <el-alert class="patient-advice" type="info" :closable="false" title="就医引导">
        {{ careAdvice }}。如皮损快速变化、反复出血、破溃或诊断不明确，建议由皮肤科医生进一步评估。
      </el-alert>

      <section class="result-box">
        <h4>可能相关方向</h4>
        <p>{{ selectedDisease?.name_cn || generation.candidate_disease }}</p>
        <p class="muted">此处为健康信息查询方向，不构成诊断结论。</p>
      </section>

      <section class="result-box">
        <h4>观察与证据匹配</h4>
        <ul v-if="generation.observation_evidence_matches.length">
          <li v-for="item in generation.observation_evidence_matches" :key="item.evidence_path">
            {{ item.evidence_text }}
            <p class="muted">来源：{{ item.source }}</p>
          </li>
        </ul>
        <p v-else>给定证据不足：观察信息未能与当前知识图谱形成明确匹配。</p>
      </section>

      <section class="result-box">
        <h4>建议关注的信息</h4>
        <ul>
          <li v-for="item in patientFriendlyEvidence" :key="item.evidence_path">
            {{ item.evidence_text }}
            <p class="muted">来源：{{ item.source }}</p>
          </li>
        </ul>
      </section>

      <el-alert class="page-section" type="warning" :closable="false" title="安全说明">
        {{ generation.disclaimer }}
      </el-alert>
    </section>
  </MainLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { getDiseases, reverseLookupByFeature } from '@/api/kg'
import { generateTemplateExplanation } from '@/api/kgRag'
import ErrorState from '@/components/ErrorState.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import type { Disease, FeatureDiseaseMatch, TemplateGeneration } from '@/types/kg'
import { adviceLevelFromText } from '@/utils/formatters'

const error = ref('')
const lookupLoading = ref(false)
const explainLoading = ref(false)
const fallbackMode = ref(false)
const diseases = ref<Disease[]>([])
const candidateMatches = ref<FeatureDiseaseMatch[]>([])
const selectedDiseaseId = ref('')
const observation = ref('')
const generation = ref<TemplateGeneration | null>(null)

const selectedDisease = computed(() => diseases.value.find((item) => item.entity_id === selectedDiseaseId.value))
const availableDiseases = computed(() =>
  candidateMatches.value.length ? candidateMatches.value.map((item) => item.disease) : diseases.value
)
const patientFriendlyEvidence = computed(() => {
  if (!generation.value) return []
  return [
    ...generation.value.supporting_evidence.slice(0, 3),
    ...generation.value.medical_advice_or_exams.slice(0, 2)
  ]
})
const careAdvice = computed(() => {
  const text = JSON.stringify(generation.value || {}, null, 0)
  return adviceLevelFromText(text)
})

async function loadDiseases() {
  try {
    diseases.value = await getDiseases()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取疾病范围失败'
  }
}

async function lookupCandidates() {
  if (!observation.value.trim()) {
    error.value = '请先填写观察信息'
    return
  }
  lookupLoading.value = true
  fallbackMode.value = false
  error.value = ''
  generation.value = null
  try {
    candidateMatches.value = await reverseLookupByFeature(observation.value.trim())
    selectedDiseaseId.value = candidateMatches.value[0]?.disease.entity_id || ''
  } catch (err) {
    candidateMatches.value = []
    fallbackMode.value = true
    selectedDiseaseId.value = ''
  } finally {
    lookupLoading.value = false
  }
}

async function generatePatientExplanation() {
  if (!observation.value.trim()) {
    error.value = '请先填写观察信息'
    return
  }
  if (!selectedDiseaseId.value) {
    error.value = '请先选择一个相关方向'
    return
  }
  explainLoading.value = true
  error.value = ''
  try {
    generation.value = await generateTemplateExplanation(selectedDiseaseId.value, observation.value.trim())
  } catch (err) {
    error.value = err instanceof Error ? err.message : '生成健康解释失败'
  } finally {
    explainLoading.value = false
  }
}

onMounted(loadDiseases)
</script>

<style scoped>
.disease-select {
  min-width: 260px;
}

.patient-advice {
  margin-bottom: 16px;
}

.result-box + .result-box {
  margin-top: 14px;
}
</style>

