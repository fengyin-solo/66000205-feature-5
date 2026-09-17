<template>
  <div class="p-4 overflow-y-auto flex-1">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-bold text-gray-300">告警记录</h2>
      <button @click="load" class="bg-gray-800 hover:bg-gray-700 rounded px-3 py-1.5 text-xs">刷新</button>
    </div>
    <p class="text-xs text-gray-500 mb-3">记录按产生时的提醒等级留存，后续调整规则不会改变历史记录，刷新页面亦不受影响。</p>

    <table class="w-full text-xs bg-gray-900 rounded-xl overflow-hidden">
      <thead>
        <tr class="text-gray-500 border-b border-gray-800 text-left">
          <th class="p-2">时间</th><th class="p-2">设备</th><th class="p-2">点位</th>
          <th class="p-2">数值</th><th class="p-2">等级</th><th class="p-2">内容</th><th class="p-2">状态</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in store.alarmRecords" :key="a.id" class="border-b border-gray-800/50">
          <td class="p-2 text-gray-500 whitespace-nowrap">{{ formatTime(a.createdAt) }}</td>
          <td class="p-2">{{ a.deviceName }}</td>
          <td class="p-2">{{ a.registerName }}</td>
          <td class="p-2">{{ a.value }}{{ a.unit }}</td>
          <td class="p-2">
            <span class="px-1.5 py-0.5 rounded" :class="LEVEL_BADGE[a.level]">{{ LEVEL_LABELS[a.level] }}</span>
          </td>
          <td class="p-2 text-gray-400">{{ a.message }}</td>
          <td class="p-2">
            <span v-if="a.acknowledged" class="text-gray-500">已确认</span>
            <button v-else @click="store.acknowledgeRecord(a.id)" class="text-blue-400 hover:underline">确认</button>
          </td>
        </tr>
        <tr v-if="!store.alarmRecords.length">
          <td colspan="7" class="p-6 text-center text-gray-600">暂无告警记录</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useModbusStore } from '../store/modbus'
import { LEVEL_BADGE, LEVEL_LABELS, formatTime } from '../labels'

const store = useModbusStore()
const load = () => store.fetchAlarmRecords()

onMounted(load)
</script>
