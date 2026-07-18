import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'role-entry',
    component: () => import('@/pages/RoleEntryPage.vue'),
    meta: { title: '角色入口' }
  },
  {
    path: '/doctor',
    name: 'doctor-dashboard',
    component: () => import('@/pages/DoctorDashboardPage.vue'),
    meta: { title: '医生工作台' }
  },
  {
    path: '/patient',
    name: 'patient-consult',
    component: () => import('@/pages/PatientConsultPage.vue'),
    meta: { title: '患者健康咨询' }
  },
  {
    path: '/kg',
    name: 'knowledge-graph',
    component: () => import('@/pages/KnowledgeGraphPage.vue'),
    meta: { title: '知识图谱查询' }
  },
  {
    path: '/kg-rag',
    name: 'kg-rag-assistant',
    component: () => import('@/pages/KGRagAssistantPage.vue'),
    meta: { title: 'KG-RAG 辅助解释' }
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/pages/NotFoundPage.vue'),
    meta: { title: '页面不存在' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.afterEach((to) => {
  document.title = `基于知识图谱增强的皮肤病智能辅助诊疗系统 - ${String(to.meta.title || '')}`
})

export default router

