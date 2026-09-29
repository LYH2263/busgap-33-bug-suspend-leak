import { ref } from 'vue'

// 停运 / 恢复后的共享刷新信号。
// 班次页保存成功后发出，事件页、时间轴、建议页（含页顶轴）一齐按
// 当前在跑班次重算：禁止只清一处，也禁止吃停运缓存。
export const dataVersion = ref(0)

export function notifyDataChanged() {
  dataVersion.value += 1
}
