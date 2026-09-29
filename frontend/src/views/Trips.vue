<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { bumpActiveScope } from '../store'
const trips = ref<any[]>([])
const events = ref<any[]>([])
const busy = ref<number | null>(null)
const error = ref('')
async function loadEvents() {
  events.value = (await api('/reports/run?line_id=1', { method: 'POST' })).events || []
}
async function refresh() {
  trips.value = await api('/trips')
  try {
    await loadEvents()
  } catch { events.value = [] }
}
onMounted(refresh)
async function toggle(r: any) {
  busy.value = r.id
  error.value = ''
  try {
    // 先等服务端确认保存，再重取列表/事件并通知各入口重算；
    // 保存失败时本地不翻转、各处仍按保存前的在跑集合展示。
    await api(`/trips/${r.id}/${r.cancelled ? 'restore' : 'cancel'}`, { method: 'POST' })
  } catch (e: any) {
    error.value = `${r.trip_no} ${r.cancelled ? '恢复' : '停运'}未保存：${e?.message || '请求失败'}`
    return
  } finally {
    busy.value = null
  }
  bumpActiveScope()
  await refresh()
}
function stripClass(s: string) {
  return s === 'bunching' ? 'bg-bunch' : s === 'large_gap' ? 'bg-large' : ''
}
function label(s: string) {
  return s === 'bunching' ? '串车' : s === 'large_gap' ? '大间隔' : '正常'
}
</script>
<template>
  <h1>班次 · 间隔条带</h1>
  <p class="sub">左侧班次清单（可停运/恢复），右侧串车/间隔竖直条带</p>
  <p v-if="error" class="badge badge-bad">{{ error }}</p>
  <div class="bg-split">
    <aside class="bg-trip-col">
      <h2>班次列表</h2>
      <div v-for="r in trips" :key="r.id ?? r.trip_no" class="bg-trip-row" :class="{ 'bg-cancelled': r.cancelled }">
        <div>
          <div>
            {{ r.trip_no }}
            <span v-if="r.cancelled" class="badge badge-bad">已停运</span>
          </div>
          <div class="bg-trip-meta">线路 {{ r.line_id }} · 车 {{ r.vehicle_no }}</div>
        </div>
        <div class="bg-trip-side">
          <div class="bg-trip-meta">{{ r.planned_depart }}</div>
          <button class="btn btn-mini" :class="{ 'btn-ghost': r.cancelled }" :disabled="busy === r.id" @click="toggle(r)">
            {{ r.cancelled ? '恢复' : '停运' }}
          </button>
        </div>
      </div>
    </aside>
    <div class="bg-strip-col">
      <article
        v-for="(e, i) in events"
        :key="i"
        class="bg-gap-strip"
        :class="stripClass(e.status)"
      >
        <header>{{ e.stop_name }}</header>
        <div class="bg-gap-body">
          <div class="bg-gap-val">{{ e.gap_min }}′</div>
          <div>计划 {{ e.planned_headway_min }}′</div>
          <div>{{ e.earlier_trip }} → {{ e.later_trip }}</div>
          <span class="badge" :class="e.status === 'bunching' ? 'badge-bad' : e.status === 'large_gap' ? 'badge-warn' : 'badge-ok'">
            {{ label(e.status) }}
          </span>
        </div>
      </article>
      <p v-if="!events.length" class="muted">暂无间隔事件</p>
    </div>
  </div>
</template>
