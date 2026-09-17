<template>
  <div class="bg-gray-900 rounded-xl p-4">
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-sm text-gray-300 font-bold">
        {{ editingId === null ? '新增点位规则' : `编辑规则 #${editingId}` }}
      </h3>
      <button v-if="open" @click="$emit('close')" class="text-xs text-gray-500 hover:text-gray-300">取消</button>
    </div>

    <div v-if="open" class="grid grid-cols-2 gap-3">
      <!-- 点位 -->
      <label class="text-xs text-gray-400">
        点位
        <input v-model="form.point" list="point-options"
          class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 text-sm text-gray-100"
          :class="fieldClass('point')" placeholder="如：温度" />
        <datalist id="point-options">
          <option v-for="p in store.meta?.points ?? []" :key="p" :value="p" />
        </datalist>
        <FieldError :msg="errors.point" />
      </label>

      <!-- 判定条件 -->
      <label class="text-xs text-gray-400">
        判定条件
        <select v-model="form.condition" class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 text-sm text-gray-100"
          :class="fieldClass('condition')">
          <option v-for="c in store.meta?.conditions ?? []" :key="c.value" :value="c.value">{{ c.label }}</option>
        </select>
        <FieldError :msg="errors.condition" />
      </label>

      <!-- 下限 -->
      <label class="text-xs text-gray-400">
        下限
        <input v-model.number="form.lowerLimit" type="number" step="any"
          class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 text-sm text-gray-100"
          :class="fieldClass('lowerLimit')" placeholder="不限制可留空" />
        <FieldError :msg="errors.lowerLimit" />
      </label>

      <!-- 上限 -->
      <label class="text-xs text-gray-400">
        上限
        <input v-model.number="form.upperLimit" type="number" step="any"
          class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 text-sm text-gray-100"
          :class="fieldClass('upperLimit')" placeholder="不限制可留空" />
        <FieldError :msg="errors.upperLimit" />
      </label>

      <!-- 提醒等级 -->
      <label class="text-xs text-gray-400">
        提醒等级
        <select v-model="form.level" class="mt-1 w-full bg-gray-800 rounded px-2 py-1.5 text-sm"
          :class="fieldClass('level')">
          <option value="info">info（提示）</option>
          <option value="warning">warning（警告）</option>
          <option value="critical">critical（严重）</option>
        </select>
        <FieldError :msg="errors.level" />
      </label>

      <!-- 生效范围 -->
      <div class="text-xs text-gray-400">
        生效范围
        <div class="mt-1 flex flex-wrap gap-2 bg-gray-800 rounded px-2 py-1.5 min-h-[34px]"
          :class="errors.scope ? 'ring-1 ring-red-500' : ''">
          <label v-for="d in store.meta?.devices ?? []" :key="d.id"
            class="flex items-center gap-1 text-gray-200 cursor-pointer">
            <input type="checkbox" :value="d.id" v-model="form.scope" />
            <span>{{ d.name }}</span>
          </label>
        </div>
        <div class="text-gray-600 mt-0.5">{{ form.scope.length ? '仅对勾选设备生效' : '未勾选 = 对全部设备生效' }}</div>
        <FieldError :msg="errors.scope" />
      </div>

      <!-- 启用 -->
      <label class="flex items-center gap-2 text-xs text-gray-300 col-span-2">
        <input type="checkbox" v-model="form.enabled" /> 规则启用（停用后该规则不再参与判定）
      </label>
    </div>

    <div v-if="open" class="flex items-center gap-2 mt-3">
      <button @click="submit()" :disabled="saving"
        class="bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white text-xs px-3 py-1.5 rounded">
        {{ saving ? '保存中...' : '保存' }}
      </button>
      <button v-if="saveError" @click="submit()" :disabled="saving"
        class="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 text-gray-200 text-xs px-3 py-1.5 rounded">
        用原请求重试
      </button>
      <span v-if="lastKey" class="text-[10px] text-gray-600">请求标识: {{ lastKey.slice(0, 13) }}…（重试复用，避免重复设置）</span>
      <span v-if="saveError" class="text-xs text-red-400 ml-auto">{{ saveError }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { h, ref } from 'vue'
import type { AlarmRule, RulePayload } from '../types'
import { useRuleStore } from '../store/rules'
import { RuleValidationError, newIdempotencyKey } from '../api'

const store = useRuleStore()

const props = defineProps<{ open: boolean; editing: AlarmRule | null }>()
const emit = defineEmits<{ close: []; saved: [] }>()

const editingId = ref<number | null>(null)
const form = ref<RulePayload>(blank())
const errors = ref<Record<string, string>>({})
const saving = ref(false)
const saveError = ref('')
const lastKey = ref('')

function blank(): RulePayload {
  return { point: '', condition: 'gt', upperLimit: null, lowerLimit: null, level: 'warning', scope: [], enabled: true }
}

// expose sync() so parent can (re)open the form
defineExpose({
  sync(rule: AlarmRule | null) {
    editingId.value = rule ? rule.id : null
    form.value = rule
      ? { point: rule.point, condition: rule.condition, upperLimit: rule.upperLimit, lowerLimit: rule.lowerLimit,
          level: rule.level, scope: [...rule.scope], enabled: rule.enabled }
      : blank()
    errors.value = {}
    saveError.value = ''
    // one key per edit session: every attempt, including retries after a
    // network failure or 400, reuses it so the server never stores duplicates
    lastKey.value = newIdempotencyKey()
  },
})

function fieldClass(field: string) {
  return errors.value[field] ? 'ring-1 ring-red-500' : ''
}

async function submit() {
  saving.value = true
  saveError.value = ''
  errors.value = {}
  try {
    const res = await store.save(editingId.value, normalize(form.value), lastKey.value)
    lastKey.value = res.key
    emit('saved')
  } catch (e) {
    if (e instanceof RuleValidationError) {
      errors.value = e.errors
      saveError.value = e.message
    } else {
      saveError.value = e instanceof Error ? e.message : String(e)
    }
  } finally {
    saving.value = false
  }
}

// empty number inputs arrive as NaN from v-model.number
function normalize(f: RulePayload): RulePayload {
  return {
    ...f,
    point: f.point.trim(),
    upperLimit: Number.isFinite(f.upperLimit as number) ? (f.upperLimit as number) : null,
    lowerLimit: Number.isFinite(f.lowerLimit as number) ? (f.lowerLimit as number) : null,
  }
}

// tiny inline render to avoid a second SFC for one span
const FieldError = (p: { msg?: string }) =>
  p.msg ? h('div', { class: 'text-red-400 text-[11px] mt-0.5' }, `⚠ ${p.msg}`) : h('div')
</script>
