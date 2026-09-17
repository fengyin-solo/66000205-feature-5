import { ref } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import type { AlarmRule, AuditEntry, RuleMeta, RulePayload } from '../types'
import { api, newIdempotencyKey, RuleValidationError } from '../api'

/**
 * Admin store for per-point alarm rules.
 * - load(): refresh rule list; the poll loop reads rules server-side, so a
 *   successful save changes judging on the next cycle with no restart.
 * - save(): generates one Idempotency-Key per submit and reuses it for the
 *   "重试" action, so a retried submit can never create duplicate rules/audits.
 */
export const useRuleStore = defineStore('rules', () => {
  const rules = ref<AlarmRule[]>([])
  const audit = ref<AuditEntry[]>([])
  const meta = ref<RuleMeta | null>(null)
  const operator = ref(localStorage.getItem('alarm.operator') || 'admin')
  const loading = ref(false)

  async function load() {
    loading.value = true
    try {
      const [r, a] = await Promise.all([api.listRules(), api.listAudit()])
      rules.value = r
      audit.value = a
      if (!meta.value) meta.value = await api.meta()
    } finally {
      loading.value = false
    }
  }

  function setOperator(name: string) {
    operator.value = name || 'admin'
    localStorage.setItem('alarm.operator', operator.value)
  }

  /**
   * @param id  existing rule id, or null to create
   * @param key caller-supplied Idempotency-Key; pass the SAME key when retrying
   */
  async function save(id: number | null, payload: RulePayload, key?: string) {
    const idemKey = key ?? newIdempotencyKey()
    const res = id
      ? await api.updateRule(id, payload, operator.value, idemKey)
      : await api.createRule(payload, operator.value, idemKey)
    await load()
    return { ...res, key: idemKey }
  }

  async function toggle(rule: AlarmRule, enabled: boolean) {
    await api.toggleRule(rule.id, enabled, operator.value)
    await load()
  }

  async function loadAudit(ruleId?: number) {
    audit.value = await api.listAudit(ruleId)
  }

  return { rules, audit, meta, operator, loading, load, save, toggle, loadAudit, setOperator }
})

/** Convenience helper for view error toasts. */
export function errorMessage(e: unknown): string {
  if (e instanceof RuleValidationError) return e.message
  if (axios.isAxiosError(e)) {
    const d = e.response?.data?.detail
    if (d && typeof d === 'object' && d.message) return d.message
    return `请求失败(${e.response?.status ?? 'network'})`
  }
  return e instanceof Error ? e.message : String(e)
}
