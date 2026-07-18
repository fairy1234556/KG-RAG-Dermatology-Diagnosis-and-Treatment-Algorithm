<template>
  <MainLayout>
    <section class="page-section">
      <div class="section-title">
        <div>
          <h3>知识图谱查询</h3>
          <p class="muted">当前覆盖 HAM10000 七类皮肤病变，证据来源于本仓库 CSV 图谱。</p>
        </div>
        <el-button :loading="loading" @click="loadBaseData">刷新数据</el-button>
      </div>

      <ErrorState :message="error" />
      <LoadingState :loading="loading" />

      <div class="grid grid-2">
        <el-form label-position="top">
          <el-form-item label="选择候选疾病">
            <el-select v-model="selectedDiseaseId" filterable placeholder="请选择疾病" @change="loadEvidence">
              <el-option
                v-for="disease in diseases"
                :key="disease.entity_id"
                :label="diseaseLabel(disease)"
                :value="disease.entity_id"
              />
            </el-select>
          </el-form-item>
          <el-button type="primary" :disabled="!selectedDiseaseId" :loading="evidenceLoading" @click="loadEvidence">
            查询疾病证据
          </el-button>
        </el-form>

        <el-form label-position="top" @submit.prevent>
          <el-form-item label="按皮损特征反查疾病">
            <el-input
              v-model="featureText"
              clearable
              placeholder="可输入实体ID、中文名、英文名或别名，例如：珍珠样结节"
              @keyup.enter="lookupFeature"
            />
          </el-form-item>
          <el-button type="success" :loading="featureLoading" @click="lookupFeature">反查候选疾病</el-button>
        </el-form>
      </div>
    </section>

    <section v-if="featureMatches.length" class="page-section">
      <div class="section-title">
        <h3>特征反查结果</h3>
        <el-tag type="warning" effect="plain">仅提示相关候选疾病，不代表诊断结果</el-tag>
      </div>
      <div class="grid grid-2">
        <el-card v-for="match in featureMatches" :key="match.evidence.triple_id" shadow="never">
          <h4>{{ match.disease.name_cn }}</h4>
          <p class="muted">{{ match.disease.name_en }} / {{ match.disease.ham10000_label }}</p>
          <p>{{ match.evidence.evidence_text }}</p>
          <div class="action-row">
            <el-button type="primary" @click="selectDisease(match.disease.entity_id)">查看该疾病证据</el-button>
            <el-button @click="$router.push({ path: '/kg-rag', query: { disease: match.disease.entity_id, observation: featureText } })">
              用于辅助解释
            </el-button>
          </div>
        </el-card>
      </div>
    </section>

    <section class="page-section">
      <div class="section-title">
        <h3>疾病证据链</h3>
        <el-tag v-if="currentDisease" type="info">{{ diseaseLabel(currentDisease) }}</el-tag>
      </div>
      <LoadingState :loading="evidenceLoading" text="正在检索图谱证据" />
      <EmptyState
        v-if="!evidenceLoading && evidenceItems.length === 0"
        description="请选择疾病后查看证据链"
      />
      <EvidenceCard v-for="item in evidenceItems" :key="item.triple_id" :evidence="item" />
    </section>
  </MainLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { getDiseaseEvidence, getDiseases, reverseLookupByFeature } from '@/api/kg'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import EvidenceCard from '@/components/EvidenceCard.vue'
import LoadingState from '@/components/LoadingState.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import type { Disease, EvidenceItem, FeatureDiseaseMatch } from '@/types/kg'
import { diseaseLabel } from '@/utils/formatters'

const route = useRoute()
const loading = ref(false)
const evidenceLoading = ref(false)
const featureLoading = ref(false)
const error = ref('')
const diseases = ref<Disease[]>([])
const selectedDiseaseId = ref('')
const featureText = ref('')
const evidenceItems = ref<EvidenceItem[]>([])
const featureMatches = ref<FeatureDiseaseMatch[]>([])

const currentDisease = computed(() => diseases.value.find((item) => item.entity_id === selectedDiseaseId.value))

async function loadBaseData() {
  loading.value = true
  error.value = ''
  try {
    diseases.value = await getDiseases()
    const queryDisease = typeof route.query.disease === 'string' ? route.query.disease : ''
    if (queryDisease) {
      selectedDiseaseId.value = queryDisease
      await loadEvidence()
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取知识图谱数据失败'
  } finally {
    loading.value = false
  }
}

async function loadEvidence() {
  if (!selectedDiseaseId.value) return
  evidenceLoading.value = true
  error.value = ''
  try {
    evidenceItems.value = await getDiseaseEvidence(selectedDiseaseId.value)
  } catch (err) {
    evidenceItems.value = []
    error.value = err instanceof Error ? err.message : '查询疾病证据失败'
  } finally {
    evidenceLoading.value = false
  }
}

async function lookupFeature() {
  if (!featureText.value.trim()) {
    error.value = '请输入皮损特征后再反查'
    return
  }
  featureLoading.value = true
  error.value = ''
  try {
    featureMatches.value = await reverseLookupByFeature(featureText.value.trim())
  } catch (err) {
    featureMatches.value = []
    error.value = err instanceof Error ? err.message : '未找到相关候选疾病'
  } finally {
    featureLoading.value = false
  }
}

function selectDisease(diseaseId: string) {
  selectedDiseaseId.value = diseaseId
  loadEvidence()
}

onMounted(loadBaseData)
</script>

