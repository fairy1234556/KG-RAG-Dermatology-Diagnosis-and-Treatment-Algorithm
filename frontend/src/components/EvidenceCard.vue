<template>
  <section class="evidence-card">
    <header class="evidence-card__header">
      <el-tag size="small" type="info">{{ evidence.triple_id }}</el-tag>
      <strong>{{ evidencePath(evidence) }}</strong>
    </header>

    <el-steps class="evidence-steps" direction="vertical" :active="3" finish-status="success">
      <el-step title="候选疾病" :description="evidence.head.name_cn" />
      <el-step title="图谱关系" :description="evidence.relation.relation_cn" />
      <el-step title="证据实体" :description="evidence.tail.name_cn" />
      <el-step title="医学来源" :description="sourceLabel(evidence)" />
    </el-steps>

    <p class="evidence-text">{{ evidence.evidence_text || '给定证据不足。' }}</p>
    <p v-if="evidence.note" class="evidence-note">备注：{{ evidence.note }}</p>
  </section>
</template>

<script setup lang="ts">
import type { EvidenceItem } from '@/types/kg'
import { evidencePath, sourceLabel } from '@/utils/formatters'

defineProps<{
  evidence: EvidenceItem
}>()
</script>

