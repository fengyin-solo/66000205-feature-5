<template>
  <div class="flex flex-col gap-4">
    <!-- header -->
    <div class="bg-gray-900 rounded-xl p-3 flex items-center gap-3 flex-wrap">
      <h2 class="text-sm font-bold text-orange-400">告警规则管理</h2>
      <div class="flex items-center gap-1 text-xs text-gray-400">
        操作人:
        <input :value="store.operator" @change="onOperator"
          class="bg-gray-800 rounded px-2 py-1 text-gray-100 w-28" list="operator-options" />
        <datalist id="operator-options">
          <option value="admin" /><option value="zhangsan" /><option value="lisi" /><option value="wangwu" />
        </datalist>
      </div>
      <button @click="openEditor(null)"
        class="ml-auto bg-orange-600 hover:bg-orange-500 text-white text-xs px-3 py-1.5 rounded">
        + 新增点位规则
      </button>
      <button @click="store.load()" class="text-xs text-gray-400 hover:text-gray-200">刷新</button>
    </div>

    <!-- editor -->
    <RuleEditor ref="editorRef" :open="editorOpen" :editing="editing" @close="editorOpen = false" @saved="onSaved" />

    <!-- rule table -->
    <div class="bg-gray-900 rounded-xl p-3 overflow-x-auto">
      <table class="w-full text-xs text-gray-200">
        <thead class="text-gray-500 text-left">
          <tr>
            <th class="py-1 pr-2">#</th><th class="pr-2">点位</th><th class="pr-2">判定条件</th>
            <th class="pr-2">下限</th><th class="pr-2">上限</th><th class="pr-2">等级</th>
            <th class="pr-2">生效范围</th><th class="pr-2">版本</th><th class="pr-2">状态</th>
            <th class="pr-2">最近修改</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in store.rules" :key="r.id" class="border-t border-gray-800 align-middle">
            <td class="py-2 pr-2 text-gray-500">{{ r.id }}</td>
            <td class="pr-2 font-bold">{{ r.point }}</td>
            <td class="pr-2">{{ conditionLabel(r.condition) }}</td>
            <td class="pr-2">{{ r.lowerLimit ?? '—' }}</td>
            <td class="pr-2">{{ r.upperLimit ?? '—' }}</td>
            <td class="pr-2"><LevelBadge :level="r.level" /></td>
            <td class="pr-2 text-gray-400">{{ scopeLabel(r.scope) }}</td>
            <td class="pr-2 text-gray-500">v{{ r.version }}</td>
            <td class="pr-2">
              <button @click="store.toggle(r, !r.enabled).catch(() => {})"
                :class="r.enabled ? 'text-green-400 hover:text-green-300' : 'text-gray-500 hover:text-gray-300'">
                {{ r.enabled ? '● 启用中' : '○ 已停用' }}
              </button>
            </td>
            <td class="pr-2 text-gray-500">{{ r.updatedBy }}<br />{{ fmt(r.updatedAt) }}</td>
            <td class="pr-2">
              <button @click="openEditor(r)" class="text-blue-400 hover:underline mr-2">编辑</button>
              <button @click="showHistory(r)" class="text-gray-400 hover:underline">历史</button>
            </td>
          </tr>
          <tr v-if="!store.rules.length">
            <td colspan="11" class="py-6 text-center text-gray-600">还没有规则，点击右上角「新增点位规则」</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- audit trail -->
    <div class="bg-gray-900 rounded-xl p-3">
      <div class="flex items-center justify-between mb-2">
        <h3 class="text-sm font-bold text-gray-300">
          变更留痕 <span v-if="historyFilter">— 规则 #{{ historyFilter.id }} {{ historyFilter.point }}</span>
          <span v-else>— 全部</span>
        </h3>
        <button v-if="historyFilter" @click="showAllHistory" class="text-xs text-gray-400 hover:text-gray-200">查看全部</button>
      </div>
      <table class="w-full text-xs">
        <thead class="text-gray-500 text-left">
          <tr><th class="py-1 pr-2">时间</th><th class="pr-2">操作人</th><th class="pr-2">点位</th><th class="pr-2">动作</th><th>改动项</th></tr>
        </thead>
        <tbody>
          <tr v-for="a in store.audit.slice(0, 50)" :key="a.id" class="border-t border-gray-800 align-top">
            <td class="py-1.5 pr-2 text-gray-400 whitespace-nowrap">{{ fmt(a.changedAt) }}</td>
            <td class="pr-2 text-gray-200">{{ a.operator }}</td>
            <td class="pr-2">{{ a.point }} <span class="text-gray-600">#{{ a.ruleId }}</span></td>
            <td class="pr-2">
              <span :class="actionClass(a.action)">{{ actionLabel(a.action) }}</span>
            </td>
            <td class="pr-2 text-gray-400">
              <span v-for="(ch, key) in a.changes" :key="key" class="inline-block mr-3">
                {{ fieldLabel(key) }}: <span class="text-red-400">{{ display(ch.old) }}</span>
                → <span class="text-green-400">{{ display(ch.new) }}</span>
              </span>
            </td>
          </tr>
          <tr v-if="!store.audit.length"><td colspan="5" class="py-4 text-center text-gray-600">暂无变更记录</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRuleStore } from '../store/rules'
import RuleEditor from './RuleEditor.vue'
import LevelBadge from './LevelBadge.vue'
import type { AlarmCondition, AlarmRule } from '../types'

const store = useRuleStore()
const editorRef = ref<InstanceType<typeof RuleEditor> | null>(null)
const editorOpen = ref(false)
const editing = ref<AlarmRule | null>(null)
const historyFilter = ref<AlarmRule | null>(null)

store.load()

function openEditor(rule: AlarmRule | null) {
  editing.value = rule
  editorOpen.value = true
  // wait for the component to render before calling exposed sync()
  requestAnimationFrame(() => editorRef.value?.sync(rule))
}

function onSaved() {
  editorOpen.value = false
  historyFilter.value = null
  store.loadAudit()
}

function onOperator(e: Event) {
  store.setOperator((e.target as HTMLInputElement).value)
}

function showHistory(r: AlarmRule) {
  historyFilter.value = r
  store.loadAudit(r.id)
}

function showAllHistory() {
  historyFilter.value = null
  store.loadAudit()
}

function conditionLabel(c: AlarmCondition) {
  return store.meta?.conditions.find(x => x.value === c)?.label ?? c
}

function scopeLabel(scope: string[]) {
  if (!scope.length) return '全部设备'
  const names = scope.map(id => store.meta?.devices.find(d => d.id === id)?.name ?? id)
  return names.join('、')
}

function actionLabel(a: string) {
  return { create: '新增', update: '修改', enable: '启用', disable: '停用' }[a] ?? a
}
function actionClass(a: string) {
  return { create: 'text-green-400', update: 'text-yellow-400', enable: 'text-blue-400', disable: 'text-gray-400' }[a] ?? ''
}
function fieldLabel(k: string) {
  return { point: '点位', condition: '条件', upperLimit: '上限', lowerLimit: '下限', level: '等级', scope: '范围', enabled: '启用' }[k] ?? k
}
function display(v: unknown): string {
  if (v === null || v === undefined) return '空'
  if (Array.isArray(v)) return v.length ? v.join(',') : '全部设备'
  if (typeof v === 'boolean') return v ? '启用' : '停用'
  return String(v)
}
function fmt(iso: string) {
  return new Date(iso).toLocaleString()
}
</script>
