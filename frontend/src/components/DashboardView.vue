<template>
  <div class="flex flex-col gap-3">
    <!-- Register Gauges -->
    <div class="grid grid-cols-4 gap-3">
      <template v-for="d in store.devices" :key="d.id">
        <div v-for="r in d.registers" :key="`${d.id}_${r.address}`" class="bg-gray-900 rounded-xl p-3">
          <div class="text-xs text-gray-400">{{ d.name }}</div>
          <div class="text-2xl font-bold" :class="d.online ? gaugeColor(r.name, r.value) : 'text-gray-600'">
            {{ typeof r.value === 'number' ? r.value.toFixed(r.value > 100 ? 0 : 1) : r.value ? 'ON' : 'OFF' }}
          </div>
          <div class="text-xs text-gray-500">{{ r.name }} {{ r.unit }}</div>
        </div>
      </template>
    </div>

    <!-- Chart -->
    <div class="bg-gray-900 rounded-xl p-3 flex-1">
      <h3 class="text-sm text-gray-400 mb-2">
        实时趋势 — {{ store.selectedDevice?.name || '选择设备' }}
      </h3>
      <TrendChart />
    </div>

    <!-- Alarm List -->
    <div class="bg-gray-900 rounded-xl p-3 max-h-48 overflow-y-auto">
      <h3 class="text-sm text-gray-400 mb-2">实时告警（历史请进入「告警记录」）</h3>
      <div v-if="!store.alarms.length" class="text-xs text-gray-600 py-2">暂无告警</div>
      <div v-for="a in store.alarms.slice(0, 10)" :key="a.id"
        class="flex justify-between text-xs bg-gray-800 rounded p-2 mb-1"
        :class="{ 'border-l-4 border-red-500': a.level === 'critical', 'border-l-4 border-yellow-500': a.level === 'warning', 'border-l-4 border-blue-500': a.level === 'info' }">
        <span>{{ a.message }}</span>
        <div class="flex gap-2">
          <span class="text-gray-500">{{ new Date(a.timestamp).toLocaleTimeString() }}</span>
          <button v-if="!a.acknowledged" @click="store.acknowledgeAlarm(a.id)" class="text-blue-400 hover:underline">确认</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useModbusStore } from '../store/modbus'
import TrendChart from './TrendChart.vue'

const store = useModbusStore()

// Mirror of the dashboard's quick visual cue: the authoritative judgement is
// server-side; this only tints the number based on current recent alarms.
function gaugeColor(point: string, value: number | boolean) {
  if (typeof value !== 'number') return 'text-orange-400'
  const active = store.alarms.some(a => a.register === point && !a.acknowledged)
  return active ? 'text-red-400' : 'text-orange-400'
}
</script>
