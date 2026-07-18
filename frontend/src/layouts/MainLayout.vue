<template>
  <el-container class="app-shell">
    <el-aside class="app-sidebar" width="264px">
      <div class="brand">
        <div class="brand-mark">KG</div>
        <div>
          <h1>{{ SYSTEM_TITLE }}</h1>
          <p>V1.0 演示模式</p>
        </div>
      </div>

      <el-menu :default-active="$route.path" router class="nav-menu">
        <el-menu-item index="/">
          <el-icon><Switch /></el-icon>
          <span>角色入口</span>
        </el-menu-item>
        <el-menu-item index="/doctor">
          <el-icon><FirstAidKit /></el-icon>
          <span>医生工作台</span>
        </el-menu-item>
        <el-menu-item index="/patient">
          <el-icon><User /></el-icon>
          <span>患者健康咨询</span>
        </el-menu-item>
        <el-menu-item index="/kg">
          <el-icon><Share /></el-icon>
          <span>知识图谱查询</span>
        </el-menu-item>
        <el-menu-item index="/kg-rag">
          <el-icon><DocumentChecked /></el-icon>
          <span>KG-RAG 辅助解释</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h2>{{ pageTitle }}</h2>
          <p>当前阶段：前后端最小业务闭环，病例保存、审核流程和真实模型调用暂未接入。</p>
        </div>
        <el-tag type="warning" effect="plain">演示模式</el-tag>
      </el-header>

      <el-main class="app-main">
        <AppDisclaimer />
        <slot />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { DocumentChecked, FirstAidKit, Share, Switch, User } from '@element-plus/icons-vue'

import AppDisclaimer from '@/components/AppDisclaimer.vue'
import { SYSTEM_TITLE } from '@/utils/formatters'

const route = useRoute()
const pageTitle = computed(() => route.meta.title || '系统首页')
</script>

