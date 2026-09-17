<template>
  <div class="p-4 overflow-y-auto flex-1">
    <div class="flex items-center justify-between mb-3">
      <h2 class="text-sm font-bold text-gray-300">阈值规则配置</h2>
      <div class="flex items-center gap-3">
        <label class="text-xs text-gray-400">
          操作人
          <input :value="store.operator" @change="store.setOperator(($event.target as HTMLInputElement).value)"
            class="ml-1 bg-gray-800 rounded px-2 py-1 text-xs w-28 outline-none focus:ring-1 ring-orange-500" />
        </label>
        <button @click="openCreate" class="bg-orange-600 hover:bg-orange-500 rounded px-3 py-1.5 text-xs">
          + 新增规则
        </button>
      </div>
    </div>
    <p class="text-xs text-gray-500 mb-3">规则保存后立即按新口径判定；历史告警记录仍按产生时的等级展示，不受调整影响。</p>

    <!-- 规则列表 -->
    <table class="w-full text-xs bg-gray-900 rounded-xl overflow-hidden">
      <thead>
        <tr class="text-gray-500 border-b border-gray-800 text-left">
          <th class="p-2">生效范围</th><th class="p-2">点位</th><th class="p-2">判定条件</th>
          <th class="p-2">下限</th><th class="p-2">上限</th><th class="p-2">提醒等级</th>
          <th class="p-2">状态</th><th class="p-2">最近修改</th><th class="p-2">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in store.rules" :key="r.id" class="border-b border-gray-800/50"
          :class="r.enabled ? '' : 'opacity-50'">
          <td class="p-2">{{ deviceLabel(r.deviceId) }}</td>
          <td class="p-2">{{ r.registerName }} <span class="text-gray-600">#{{ r.registerAddress }}</span></td>
          <td class="p-2">{{ CONDITION_LABELS[r.condition] }}</td>
          <td class="p-2">{{ r.lowerLimit ?? '-' }}</td>
          <td class="p-2">{{ r.upperLimit ?? '-' }}</td>
          <td class="p-2">
            <span class="px-1.5 py-0.5 rounded" :class="LEVEL_BADGE[r.level]">{{ LEVEL_LABELS[r.level] }}</span>
          </td>
          <td class="p-2">
            <button @click="store.toggleRule(r)"
              class="px-2 py-0.5 rounded text-xs"
              :class="r.enabled ? 'bg-green-900/60 text-green-300' : 'bg-gray-800 text-gray-500'">
              {{ r.enabled ? '生效中' : '已停用' }}
            </button>
          </td>
          <td class="p-2 text-gray-500">{{ r.updatedBy || r.createdBy }} · {{ formatTime(r.updatedAt || r.createdAt) }}</td>
          <td class="p-2 whitespace-nowrap">
            <button @click="openEdit(r)" class="text-blue-400 hover:underline mr-2">编辑</button>
            <button @click="remove(r)" class="text-red-400 hover:underline">删除</button>
          </td>
        </tr>
        <tr v-if="!store.rules.length">
          <td colspan="9" class="p-6 text-center text-gray-600">暂无规则，点击「新增规则」创建</td>
        </tr>
      </tbody>
    </table>

    <!-- 新增 / 编辑表单 -->
    <div v-if="showForm" class="fixed inset-0 bg-black/60 flex items-center justify-center z-10" @click.self="showForm = false">
      <div class="bg-gray-900 rounded-xl p-5 w-[26rem] border border-gray-700">
        <h3 class="text-sm font-bold text-gray-200 mb-4">{{ editingId ? '编辑规则' : '新增规则' }}</h3>

        <div v-if="saveError" class="bg-red-900/40 text-red-300 text-xs rounded p-2 mb-3">{{ saveError }}</div>

        <div class="flex flex-col gap-3 text-xs">
          <label class="block">
            <span class="text-gray-400">生效范围（设备）</span>
            <select v-model="form.deviceId" @change="onDeviceChange"
              class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500">
              <option value="*">全部设备</option>
              <option v-for="d in store.devices" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
            <span v-if="fieldErrors.deviceId" class="text-red-400 block mt-0.5">{{ fieldErrors.deviceId }}</span>
          </label>

          <div class="flex gap-3">
            <label class="block flex-1">
              <span class="text-gray-400">点位名称</span>
              <select v-if="form.deviceId !== '*'" v-model="form.registerName" @change="onRegisterChange"
                class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500">
                <option value="" disabled>选择点位</option>
                <option v-for="reg in deviceRegisters" :key="reg.address" :value="reg.name">{{ reg.name }}</option>
              </select>
              <input v-else v-model.trim="form.registerName" list="all-register-names" placeholder="如：温度"
                class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500" />
              <datalist id="all-register-names">
                <option v-for="n in allRegisterNames" :key="n" :value="n" />
              </datalist>
              <span v-if="fieldErrors.registerName" class="text-red-400 block mt-0.5">{{ fieldErrors.registerName }}</span>
            </label>
            <label class="block w-28">
              <span class="text-gray-400">寄存器地址</span>
              <input v-model.number="form.registerAddress" type="number" min="0"
                class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500" />
              <span v-if="fieldErrors.registerAddress" class="text-red-400 block mt-0.5">{{ fieldErrors.registerAddress }}</span>
            </label>
          </div>

          <label class="block">
            <span class="text-gray-400">判定条件</span>
            <select v-model="form.condition"
              class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500">
              <option v-for="(label, key) in CONDITION_LABELS" :key="key" :value="key">{{ label }}</option>
            </select>
          </label>

          <div class="flex gap-3">
            <label class="block flex-1">
              <span class="text-gray-400">下限{{ needLower ? '（必填）' : '（可选）' }}</span>
              <input v-model.number="form.lowerLimit" type="number" step="any" placeholder="留空表示不限制"
                class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500"
                :class="fieldErrors.lowerLimit ? 'ring-1 ring-red-500' : ''" />
              <span v-if="fieldErrors.lowerLimit" class="text-red-400 block mt-0.5">{{ fieldErrors.lowerLimit }}</span>
            </label>
            <label class="block flex-1">
              <span class="text-gray-400">上限{{ needUpper ? '（必填）' : '（可选）' }}</span>
              <input v-model.number="form.upperLimit" type="number" step="any" placeholder="留空表示不限制"
                class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500"
                :class="fieldErrors.upperLimit ? 'ring-1 ring-red-500' : ''" />
              <span v-if="fieldErrors.upperLimit" class="text-red-400 block mt-0.5">{{ fieldErrors.upperLimit }}</span>
            </label>
          </div>

          <div class="flex gap-3 items-end">
            <label class="block flex-1">
              <span class="text-gray-400">提醒等级</span>
              <select v-model="form.level"
                class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 outline-none focus:ring-1 ring-orange-500">
                <option v-for="(label, key) in LEVEL_LABELS" :key="key" :value="key">{{ label }}</option>
              </select>
            </label>
            <label class="flex items-center gap-2 pb-1.5">
              <input type="checkbox" v-model="form.enabled" class="accent-orange-500" />
              <span class="text-gray-400">保存后生效</span>
            </label>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-5">
          <button @click="showForm = false" class="px-3 py-1.5 rounded text-xs bg-gray-800 hover:bg-gray-700">取消</button>
          <button @click="submit" :disabled="saving"
            class="px-3 py-1.5 rounded text-xs bg-orange-600 hover:bg-orange-500 disabled:opacity-50">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useModbusStore } from '../store/modbus'
import { CONDITION_LABELS, LEVEL_BADGE, LEVEL_LABELS, formatTime } from '../labels'
import type { ThresholdCondition, ThresholdRule } from '../types'

const store = useModbusStore()

const showForm = ref(false)
const editingId = ref<string | null>(null)
// 一次新增会话的幂等键：保存失败重试时保持不变，服务端据此去重
const clientRequestId = ref<string | null>(null)
const saving = ref(false)
const saveError = ref('')
const fieldErrors = ref<Record<string, string>>({})

const emptyForm = () => ({
  deviceId: '*',
  registerAddress: 0,
  registerName: '',
  lowerLimit: null as number | null | '',
  upperLimit: null as number | null | '',
  condition: 'above_upper' as ThresholdCondition,
  level: 'warning' as const,
  enabled: true,
  operator: '',
})
const form = reactive(emptyForm())

const needLower = computed(() => form.condition === 'below_lower' || form.condition === 'out_of_range' || form.condition === 'in_range')
const needUpper = computed(() => form.condition === 'above_upper' || form.condition === 'out_of_range' || form.condition === 'in_range')

const deviceRegisters = computed(() =>
  store.devices.find(d => d.id === form.deviceId)?.registers.filter(r => typeof r.value === 'number') ?? []
)
const allRegisterNames = computed(() =>
  [...new Set(store.devices.flatMap(d => d.registers.filter(r => typeof r.value === 'number').map(r => r.name)))]
)

function deviceLabel(deviceId: string) {
  if (deviceId === '*') return '全部设备'
  return store.devices.find(d => d.id === deviceId)?.name || deviceId
}

function onDeviceChange() {
  form.registerName = ''
  form.registerAddress = 0
}

function onRegisterChange() {
  const reg = deviceRegisters.value.find(r => r.name === form.registerName)
  if (reg) form.registerAddress = reg.address
}

function openCreate() {
  Object.assign(form, emptyForm())
  editingId.value = null
  clientRequestId.value = crypto.randomUUID()
  clearErrors()
  showForm.value = true
}

function openEdit(rule: ThresholdRule) {
  Object.assign(form, {
    deviceId: rule.deviceId,
    registerAddress: rule.registerAddress,
    registerName: rule.registerName,
    lowerLimit: rule.lowerLimit,
    upperLimit: rule.upperLimit,
    condition: rule.condition,
    level: rule.level,
    enabled: rule.enabled,
    operator: '',
  })
  editingId.value = rule.id
  clientRequestId.value = null
  clearErrors()
  showForm.value = true
}

function clearErrors() {
  fieldErrors.value = {}
  saveError.value = ''
}

const toNum = (v: number | null | '') => (v === '' || v === null || Number.isNaN(v) ? null : Number(v))

async function submit() {
  saving.value = true
  clearErrors()
  const res = await store.saveRule(
    { ...form, lowerLimit: toNum(form.lowerLimit), upperLimit: toNum(form.upperLimit) },
    editingId.value,
    clientRequestId.value,
  )
  saving.value = false
  if (res.ok) {
    showForm.value = false
    return
  }
  // 校验未通过：把错误标到对应表单项上；保存失败时 clientRequestId 不变，重试不产生重复
  for (const e of res.errors) fieldErrors.value[e.field] = e.message
  if (!res.errors.length) saveError.value = res.message
}

async function remove(rule: ThresholdRule) {
  if (!confirm(`确认删除「${deviceLabel(rule.deviceId)} / ${rule.registerName}」的这条规则？`)) return
  await store.deleteRule(rule.id)
}

onMounted(() => store.fetchRules())
</script>
