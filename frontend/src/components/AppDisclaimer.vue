<template>
  <el-alert
    class="app-disclaimer"
    type="warning"
    :closable="false"
    show-icon
    title="医学安全提示"
  >
    <template #default>
      <span>{{ MEDICAL_DISCLAIMER }}</span>
    </template>
  </el-alert>
</template>

<script setup lang="ts">
import { MEDICAL_DISCLAIMER } from '@/utils/formatters'
</script>

