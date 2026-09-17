<template>
  <div class="flex h-screen">
    <!-- Sidebar -->
    <div class="w-64 bg-gray-900 p-4 flex flex-col gap-3 border-r border-gray-800 overflow-y-auto">
      <h1 class="text-lg font-bold text-orange-400">Modbus 工业监控</h1>

      <div class="flex flex-col gap-1 text-sm">
        <button v-for="t in tabs" :key="t.key" @click="activeTab = t.key"
          class="text-left rounded px-2 py-1.5"
          :class="activeTab === t.key ? 'bg-orange-600/20 text-orange-300 ring-1 ring-orange-700' : 'text-gray-400 hover:bg-gray-800'">
          {{ t.label }}
        </button>
      </div>

      <template v-if="activeTab === 'dashboard'">
        <div class="flex gap-2">
          <button @click="startPoll" :disabled="store.isPolling" class="flex-1 bg-green-700 py-1.5 rounded text-xs hover:bg-green-600 disabled:opacity-50">
            {{ store.isPolling ? '采集中...' : '开始采集' }}
          </button>
          <button @click="stopPoll" :disabled="!store.isPolling" class="flex-1 bg-red-700 py-1.5 rounded text-xs hover:bg-red-600 disabled:opacity-50">
            停止
          </button>
        </div>
        <div>
          <label class="text-gray-400 text-xs">轮询间隔: {{ store.pollInterval }}ms</label>
          <input type="range" v-model.number="store.pollInterval" min="200" max="5000" step="100" class="w-full" />
        </div>
        <div v-if="!store.backendOnline" class="text-[11px] text-red-400 bg-red-900/30 rounded px-2 py-1">
          后端未连接，判定结果暂不可用
        </div>

        <h3 class="text-gray-400 text-xs mt-2">设备列表</h3>
        <div v-for="d in store.devices" :key="d.id" @click="store.selectedDevice = d"
          class="bg-gray-800 rounded p-2 cursor-pointer text-sm"
          :class="store.selectedDevice?.id === d.id ? 'ring-1 ring-orange-500' : ''">
          <div class="flex justify-between">
            <span>{{ d.name }}</span>
            <span class="w-2 h-2 rounded-full mt-1.5" :class="d.online ? 'bg-green-500' : 'bg-red-500'"></span>
          </div>
          <div class="text-xs text-gray-500">{{ d.ip }}:{{ d.port }} [{{ d.slaveId }}]</div>
        </div>

        <div v-if="store.criticalAlarms.length" class="bg-red-900/50 rounded p-2 mt-2">
          <h4 class="text-red-400 text-xs font-bold">⚠ 严重告警 {{ store.criticalAlarms.length }}</h4>
          <div v-for="a in store.criticalAlarms.slice(0, 3)" :key="a.id" class="text-xs text-red-300 mt-1 truncate">
            {{ a.message }}
          </div>
        </div>

        <div class="text-xs text-gray-600 mt-auto">
          在线: {{ store.onlineDevices.length }}/{{ store.devices.length }}
        </div>
      </template>
    </div>

    <!-- Main -->
    <div class="flex-1 flex flex-col gap-3 p-4 overflow-y-auto">
      <DashboardView v-if="activeTab === 'dashboard'" />
      <AlarmCenter v-else-if="activeTab === 'alarms'" ref="alarmCenterRef" v-show="activeTab === 'alarms'" />
      <RuleAdmin v-else-if="activeTab === 'rules'" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useModbusStore } from './store/modbus'
import DashboardView from './components/DashboardView.vue'
import AlarmCenter from './components/AlarmCenter.vue'
import RuleAdmin from './components/RuleAdmin.vue'

const store = useModbusStore()
const activeTab = ref<'dashboard' | 'alarms' | 'rules'>('dashboard')
const alarmCenterRef = ref<InstanceType<typeof AlarmCenter> | null>(null)
const tabs = [
  { key: 'dashboard' as const, label: '监控大屏' },
  { key: 'alarms' as const, label: '告警记录' },
  { key: 'rules' as const, label: '规则管理' },
]

let timer: number | null = null

async function tick() {
  await store.pollOnce()
}

function startPoll() {
  store.isPolling = true
  tick()
  timer = window.setInterval(tick, store.pollInterval)
}

function stopPoll() {
  store.isPolling = false
  if (timer) { clearInterval(timer); timer = null }
}

// apply changed interval while running
watch(() => store.pollInterval, () => {
  if (store.isPolling) {
    stopPoll()
    startPoll()
  }
})

// opening the alarm-center entry re-fetches; records still render with their
// original snapshotted levels no matter what changed since
watch(activeTab, (t) => {
  if (t === 'alarms') alarmCenterRef.value?.load()
})

onMounted(() => store.initMockDevices())
onUnmounted(() => stopPoll())
</script>
