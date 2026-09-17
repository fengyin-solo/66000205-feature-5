import type { AlarmLevel, ThresholdCondition } from './types'

export const CONDITION_LABELS: Record<ThresholdCondition, string> = {
  above_upper: '高于上限',
  below_lower: '低于下限',
  out_of_range: '超出上下限范围',
  in_range: '处于上下限范围内',
}

export const LEVEL_LABELS: Record<AlarmLevel, string> = {
  info: '提示',
  warning: '警告',
  critical: '严重',
}

export const LEVEL_BADGE: Record<AlarmLevel, string> = {
  info: 'bg-blue-900/60 text-blue-300',
  warning: 'bg-yellow-900/60 text-yellow-300',
  critical: 'bg-red-900/60 text-red-300',
}

export const AUDIT_ACTION_LABELS: Record<string, string> = {
  create: '新增',
  update: '修改',
  delete: '删除',
}

/** 审计记录中字段名 -> 中文名 */
export const RULE_FIELD_LABELS: Record<string, string> = {
  deviceId: '生效范围',
  registerAddress: '寄存器地址',
  registerName: '点位名称',
  lowerLimit: '下限',
  upperLimit: '上限',
  condition: '判定条件',
  level: '提醒等级',
  enabled: '启用状态',
}

export function formatTime(ts: number | null | undefined): string {
  if (!ts) return '-'
  return new Date(ts).toLocaleString()
}
