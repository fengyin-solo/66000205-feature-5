<template>
  <div class="flex flex-col gap-4">
    <div class="bg-gray-900 rounded-xl p-3 flex items-center gap-3 flex-wrap">
      <h2 class="text-sm font-bold text-orange-400">告警记录</h2>
      <span class="text-[11px] text-gray-500">记录中的等级为触发当时的规则快照，之后修改规则不会改变历史展示</span>
      <select v-model="filters.level" @change="load" class="bg-gray-800 text-xs rounded px-2 py-1 text-gray-200">
        <option value="">全部等级</option>
        <option value="critical">critical</option>
        <option value="warning">warning</option>
        <option value="info">info</option>
      </select>
      <select v-model="filters.point" @change="load" class="bg-gray-800 text-xs rounded px-2 py-1 text-gray-200">
        <option value="">全部点位</option>
        <option v-for="p in points" :key="p" :value="p">{{ p }}</option>
      </select>
      <label class="text-xs text-gray-400 flex items-center gap-1">
        <input type="checkbox" v-model="onlyUnacked" @change="load" /> 仅未确认
      </label>
      <button @click="load" class="ml-auto text-xs text-gray-400 hover:text-gray-200">刷新</button>
    </div>

    <div class="bg-gray-900 rounded-xl p-3 overflow-x-auto">
      <table class="w-full text-xs text-gray-200">
        <thead class="text-gray-500 text-left">
          <tr>
            <th class="py-1 pr-2">时间</th><th class="pr-2">设备</th><th class="pr-2">点位</th>
            <th class="pr-2">实测值</th><th class="pr-2">等级(快照)</th><th class="pr-2">依据规则</th>
            <th class="pr-2">描述</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="a in records" :key="a.id" class="border-t border-gray-800 align-middle"
            :class="{ 'opacity-50': a.acknowledged }">
            <td class="py-2 pr-2 text-gray-400 whitespace-nowrap">{{ fmt(a.raisedAt) }}</td>
            <td class="pr-2">{{ a.deviceName ?? a.deviceId ?? '—' }}</td>
            <td class="pr-2 font-bold">{{ a.point }}</td>
            <td class="pr-2">{{ a.value }} {{ a.unit }}</td>
            <td class="pr-2"><LevelBadge :level="a.level" /></td>
            <td class="pr-2 text-gray-500">
              <template v-if="a.ruleId">规则#{{ a.ruleId }} v{{ a.ruleVersion }}</template>
              <template v-else>—</template>
            </td>
            <td class="pr-2 text-gray-400">{{ a.message }}</td>
            <td class="pr-2">
              <button v-if="!a.acknowledged" @click="ack(a.id)" class="text-blue-400 hover:underline">确认</button>
              <span v-else class="text-gray-600">已确认</span>
            </td>
          </tr>
          <tr v-if="!records.length">
            <td colspan="8" class="py-8 text-center text-gray-600">暂无告警记录（开始采集后按当前规则产生）</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import LevelBadge from './LevelBadge.vue'
import type { AlarmRecord } from '../types'

const records = ref<AlarmRecord[]>([])
const points = ref<string[]>([])
const filters = ref({ level: '', point: '' })
const onlyUnacked = ref(false)

async function load() {
  const params: Record<string, unknown> = { limit: 300 }
  if (filters.value.level) params.level = filters.value.level
  if (filters.value.point) params.point = filters.value.point
  if (onlyUnacked.value) params.acknowledged = false
  records.value = await api.listAlarms(params)
}

async function ack(id: number) {
  await api.ackAlarm(id)
  await load()
}

function fmt(iso: string) {
  return new Date(iso).toLocaleString()
}

onMounted(async () => {
  try {
    const meta = await api.meta()
    points.value = meta.points
  } catch { /* backend offline */ }
  await load()
})
defineExpose({ load })
</script>
