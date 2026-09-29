export function unifyStatusLabel(status: string): string {
  if (status === 'bunching') return '串车'
  if (status === 'large_gap') return '大间隔'
  return '正常'
}
