<template>
  <div v-if="loading" class="state-box">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>{{ text }}</span>
  </div>
</template>

<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue'

withDefaults(
  defineProps<{
    loading: boolean
    text?: string
  }>(),
  {
    text: '正在加载，请稍候'
  }
)
</script>

