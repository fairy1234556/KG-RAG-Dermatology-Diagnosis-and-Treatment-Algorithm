<template>
  <el-alert v-if="message" type="error" :closable="false" show-icon :title="title">
    <template #default>{{ message }}</template>
  </el-alert>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title?: string
    message: string
  }>(),
  {
    title: '请求失败'
  }
)
</script>

