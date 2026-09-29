import { ref } from 'vue'

// 停运/恢复保存成功后 +1：所有按“当前在跑班次”计算的入口
// （报告事件、时间轴、建议、头部发车间隔轴）都要据此重取，
// 禁止任何入口继续吃停运前的旧集合。保存失败不得 bump。
export const activeScopeVersion = ref(0)

export function bumpActiveScope() {
  activeScopeVersion.value += 1
}
