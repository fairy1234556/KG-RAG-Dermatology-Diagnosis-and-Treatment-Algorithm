<template>
  <MainLayout>
    <section class="page-section">
      <el-empty description="页面不存在">
        <el-button type="primary" @click="$router.push('/')">返回角色入口</el-button>
      </el-empty>
    </section>
  </MainLayout>
</template>

<script setup lang="ts">
import MainLayout from '@/layouts/MainLayout.vue'
</script>

