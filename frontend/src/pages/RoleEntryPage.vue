<template>
  <MainLayout>
    <section class="page-section">
      <div class="section-title">
        <div>
          <h3>请选择演示入口</h3>
          <p class="muted">本阶段采用无登录角色入口，账号密码、权限数据库和真实病例持久化暂未接入。</p>
        </div>
        <el-tag type="info">第二阶段最小闭环</el-tag>
      </div>

      <div class="grid grid-3">
        <el-card v-for="role in roles" :key="role.path" shadow="never">
          <h4>{{ role.title }}</h4>
          <p class="muted">{{ role.description }}</p>
          <el-button class="role-button" type="primary" @click="enter(role.path, role.code)">
            进入{{ role.title }}
          </el-button>
        </el-card>
      </div>
    </section>

    <section class="page-section">
      <div class="section-title">
        <h3>系统运行状态</h3>
        <el-button :loading="loading" @click="loadStatus">刷新状态</el-button>
      </div>
      <ErrorState :message="error" />
      <LoadingState :loading="loading" text="正在读取后端与图谱状态" />
      <div v-if="health && kgStatus" class="grid grid-3">
        <div>
          <p class="muted">后端服务</p>
          <div class="status-number">{{ health.service_status === 'ok' ? '正常' : '异常' }}</div>
        </div>
        <div>
          <p class="muted">图谱实体</p>
          <div class="status-number">{{ kgStatus.entity_count }}</div>
        </div>
        <div>
          <p class="muted">七类疾病</p>
          <div class="status-number">{{ kgStatus.disease_count }}</div>
        </div>
      </div>
      <el-alert
        v-if="kgStatus?.warnings?.length"
        class="page-section"
        type="warning"
        :closable="false"
        title="图谱质量提示"
      >
        <ul>
          <li v-for="warning in kgStatus.warnings" :key="warning">{{ warning }}</li>
        </ul>
      </el-alert>
    </section>
  </MainLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { getHealth, getKgStatus } from '@/api/kg'
import ErrorState from '@/components/ErrorState.vue'
import LoadingState from '@/components/LoadingState.vue'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAppStore, type RoleCode } from '@/stores/app'
import type { KgStatus } from '@/types/kg'

interface HealthStatus {
  service_status: string
  system_version: string
  kg_loaded: boolean
  kg_warnings: string[]
}

const router = useRouter()
const appStore = useAppStore()
const loading = ref(false)
const error = ref('')
const health = ref<HealthStatus | null>(null)
const kgStatus = ref<KgStatus | null>(null)

const roles: Array<{ title: string; code: RoleCode; path: string; description: string }> = [
  {
    title: '医生端',
    code: 'doctor',
    path: '/doctor',
    description: '面向皮肤科医生，查看候选疾病、图谱证据和辅助解释。'
  },
  {
    title: '患者端',
    code: 'patient',
    path: '/patient',
    description: '用于健康信息咨询和就医引导，不提供确定性诊断。'
  },
  {
    title: '知识图谱',
    code: 'knowledge_admin',
    path: '/kg',
    description: '查询 HAM10000 七类疾病证据路径和医学来源。'
  }
]

function enter(path: string, role: RoleCode) {
  appStore.setRole(role)
  router.push(path)
}

async function loadStatus() {
  loading.value = true
  error.value = ''
  try {
    const [healthResult, kgResult] = await Promise.all([getHealth(), getKgStatus()])
    health.value = healthResult
    kgStatus.value = kgResult
  } catch (err) {
    error.value = err instanceof Error ? err.message : '读取状态失败'
  } finally {
    loading.value = false
  }
}

onMounted(loadStatus)
</script>

<style scoped>
.role-button {
  margin-top: 14px;
}
</style>

