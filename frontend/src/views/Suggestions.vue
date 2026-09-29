<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '../api'
import { dataVersion } from '../refresh'
const tips = ref<any[]>([])
async function load() {
  tips.value = (await api('/reports/suggestions?line_id=1')).suggestions || []
}
onMounted(load)
watch(dataVersion, load)
</script>
<template>
  <h1>建议</h1>
  <p class="sub">以下仅为在跑班次的调班提示，点名班次与报告事件一一对应</p>
  <div class="card" v-for="(t,i) in tips" :key="i">
    <div><strong>{{ t.stop_name }}</strong> · {{ t.earlier_trip }} → {{ t.later_trip }} · 间隔 {{ t.gap_min }} 分</div>
    <p class="muted">{{ t.suggestion }}</p>
  </div>
  <p v-if="!tips.length" class="muted">暂无异常建议</p>
</template>
