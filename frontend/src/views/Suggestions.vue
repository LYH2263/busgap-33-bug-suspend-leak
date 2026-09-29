<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { activeScopeVersion } from '../store'
const tips = ref<any[]>([])
async function load() {
  tips.value = (await api('/reports/suggestions?line_id=1')).suggestions || []
}
onMounted(load)
// 停运/恢复生效后建议按当前在跑班次重算，停运班不再被点名
watch(activeScopeVersion, load)
</script>
<template>
  <h1>建议</h1>
  <p class="sub">仅针对当前在跑班次生成，点名班次均可在串车报告事件中对上</p>
  <div class="card" v-for="(t,i) in tips" :key="i">
    <div><strong>{{ t.stop_name }}</strong> · {{ t.earlier_trip }} → {{ t.later_trip }} · 间隔 {{ t.gap_min }} 分</div>
    <p class="muted">{{ t.suggestion }}</p>
  </div>
  <p v-if="!tips.length" class="muted">暂无异常建议</p>
</template>
