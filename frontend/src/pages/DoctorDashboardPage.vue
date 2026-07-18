<template>
  <MainLayout>
    <section class="page-section">
      <div class="section-title">
        <div>
          <h3>医生工作台</h3>
          <p class="muted">当前为演示模式：病例保存、医生审核、报告版本和自动一致性校验暂未接入。</p>
        </div>
        <el-button :loading="loading" @click="loadData">刷新</el-button>
      </div>

      <ErrorState :message="error" />
      <LoadingState :loading="loading" />

      <div v-if="kgStatus" class="grid grid-3">
        <div>
          <p class="muted">有效实体</p>
          <div class="status-number">{{ kgStatus.entity_count }}</div>
        </div>
        <div>
          <p class="muted">三元组证据</p>
          <div class="status-number">{{ kgStatus.triple_count }}</div>
        </div>
        <div>
          <p class="muted">证据来源</p>
          <div class="status-number">{{ kgStatus.source_count }}</div>
        </div>
      </div>
    </section>

    <section class="page-section">
      <div class="section-title">
        <h3>HAM10000 七类候选疾病范围</h3>
        <el-tag type="warning" effect="plain">评分排序暂未接入</el-tag>
      </div>
      <EmptyState v-if="!loading && diseases.length === 0" description="暂无疾病数据" />
      <div class="grid grid-2">
        <el-card v-for="disease in diseases" :key="disease.entity_id" shadow="never">
          <h4>{{ disease.name_cn }}</h4>
          <p class="muted">{{ disease.name_en }} / {{ disease.ham10000_label }}</p>
          <div class="action-row">
            <el-button type="primary" @click="$router.push({ path: '/kg', query: { disease: disease.entity_id } })">
              查看图谱证据
            </el-button>
            <el-button @click="$router.push({ path: '/kg-rag', query: { disease: disease.entity_id } })">
              生成辅助解释
            </el-button>
          </div>
        </el-card>
      </div>
    </section>

    <section class="page-section">
      <div class="section-title">
        <h3>本阶段能力边界</h3>
      </div>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="已接入">
          图谱状态、疾病列表、疾病证据、特征反查、证据上下文、Prompt 构造、模板辅助解释。
        </el-descriptions-item>
        <el-descriptions-item label="暂未接入">
          真实病例保存、候选排序评分、医生审核、报告导出、真实大模型调用、图片分类。
        </el-descriptions-item>
      </el-descriptions>
    </section>
  </MainLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getDiseases, getKgStatus } from '@/api/kg'
import EmptyState from '@/components/EmptyState.vue'
import ErrorState from '@/components/ErrorState.vue'
import LoadingState from '@/components/LoadingState.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import type { Disease, KgStatus } from '@/types/kg'

const loading = ref(false)
const error = ref('')
const diseases = ref<Disease[]>([])
const kgStatus = ref<KgStatus | null>(null)

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [statusResult, diseaseResult] = await Promise.all([getKgStatus(), getDiseases()])
    kgStatus.value = statusResult
    diseases.value = diseaseResult
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取医生工作台数据失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>

