<template>
  <div class="p-4 overflow-y-auto flex-1">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-bold text-gray-300">规则变更记录</h2>
      <button @click="load" class="bg-gray-800 hover:bg-gray-700 rounded px-3 py-1.5 text-xs">刷新</button>
    </div>
    <p class="text-xs text-gray-500 mb-3">谁在什么时候改了哪一项，均可在此回看。</p>

    <div v-for="a in store.ruleAudits" :key="a.id" class="bg-gray-900 rounded-xl p-3 mb-2 text-xs">
      <div class="flex items-center gap-2 mb-1.5">
        <span class="px-1.5 py-0.5 rounded"
          :class="a.action === 'create' ? 'bg-green-900/60 text-green-300' : a.action === 'delete' ? 'bg-red-900/60 text-red-300' : 'bg-blue-900/60 text-blue-300'">
          {{ AUDIT_ACTION_LABELS[a.action] || a.action }}
        </span>
        <span class="text-gray-300 font-bold">{{ a.operator }}</span>
        <span class="text-gray-500">{{ formatTime(a.createdAt) }}</span>
        <span class="text-gray-600">{{ ruleTitle(a) }}</span>
      </div>
      <div v-if="a.action === 'update'" class="flex flex-col gap-0.5">
        <div v-for="f in a.changedFields" :key="f" class="text-gray-400">
          <span class="text-gray-500">{{ RULE_FIELD_LABELS[f] || f }}：</span>
          <span class="text-red-300/80 line-through">{{ fieldValue(a.before, f) }}</span>
          <span class="mx-1 text-gray-600">→</span>
          <span class="text-green-300/80">{{ fieldValue(a.after, f) }}</span>
        </div>
      </div>
      <div v-else-if="a.action === 'create'" class="text-gray-500">
        {{ describe(a.after) }}
      </div>
      <div v-else class="text-gray-500">
        删除前配置：{{ describe(a.before) }}
      </div>
    </div>
    <div v-if="!store.ruleAudits.length" class="text-center text-gray-600 text-xs p-6">暂无变更记录</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useModbusStore } from '../store/modbus'
import { AUDIT_ACTION_LABELS, CONDITION_LABELS, LEVEL_LABELS, RULE_FIELD_LABELS, formatTime } from '../labels'
import type { RuleAudit, ThresholdCondition, ThresholdRule } from '../types'

const store = useModbusStore()
const load = () => store.fetchAudits()

function ruleTitle(a: RuleAudit) {
  const r = a.after || a.before
  if (!r) return ''
  const dev = r.deviceId === '*' ? '全部设备' : (store.devices.find(d => d.id === r.deviceId)?.name || r.deviceId)
  return `（${dev} / ${r.registerName}）`
}

function fieldValue(rule: Partial<ThresholdRule> | null | undefined, field: string): string {
  if (!rule) return '-'
  const v = (rule as any)[field]
  if (field === 'deviceId') return v === '*' ? '全部设备' : (store.devices.find(d => d.id === v)?.name || v)
  if (field === 'condition') return CONDITION_LABELS[v as ThresholdCondition] || v
  if (field === 'level') return LEVEL_LABELS[v as keyof typeof LEVEL_LABELS] || v
  if (field === 'enabled') return v ? '生效' : '停用'
  return v === null || v === undefined ? '-' : String(v)
}

function describe(rule: Partial<ThresholdRule> | null | undefined): string {
  if (!rule) return '-'
  const parts = [
    `条件：${CONDITION_LABELS[rule.condition as ThresholdCondition] || rule.condition}`,
    rule.lowerLimit != null ? `下限 ${rule.lowerLimit}` : null,
    rule.upperLimit != null ? `上限 ${rule.upperLimit}` : null,
    `等级：${LEVEL_LABELS[rule.level as keyof typeof LEVEL_LABELS] || rule.level}`,
    rule.enabled === false ? '停用' : '生效',
  ]
  return parts.filter(Boolean).join('，')
}

onMounted(load)
</script>
