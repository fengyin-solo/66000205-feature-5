import axios from 'axios'
import type { AlarmRecord, AlarmRule, AuditEntry, RuleMeta, RulePayload } from '../types'

const http = axios.create({ baseURL: '/api' })

export class RuleValidationError extends Error {
  errors: Record<string, string>
  constructor(errors: Record<string, string>, message: string) {
    super(message)
    this.errors = errors
  }
}

/** Build an Idempotency-Key the caller can reuse across retries. */
export function newIdempotencyKey() {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `idem-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

async function save(path: string, payload: RulePayload, operator: string, key: string, method: 'post' | 'put') {
  try {
    const res = await http.request({
      url: path,
      method,
      data: payload,
      headers: { 'X-Operator': operator, 'Idempotency-Key': key },
    })
    return res.data as { rule: AlarmRule; action: 'create' | 'update' }
  } catch (e: unknown) {
    if (axios.isAxiosError(e) && e.response?.status === 400) {
      const detail = e.response.data.detail
      if (detail && typeof detail === 'object' && detail.errors) {
        throw new RuleValidationError(detail.errors, detail.message ?? '校验未通过')
      }
    }
    throw e
  }
}

export const api = {
  meta: () => http.get<RuleMeta>('/alarm/meta').then(r => r.data),
  listRules: () => http.get<AlarmRule[]>('/alarm/rules').then(r => r.data),
  createRule: (p: RulePayload, operator: string, key: string) => save('/alarm/rules', p, operator, key, 'post'),
  updateRule: (id: number, p: RulePayload, operator: string, key: string) => save(`/alarm/rules/${id}`, p, operator, key, 'put'),
  toggleRule: (id: number, enabled: boolean, operator: string) =>
    http.post(`/alarm/rules/${id}/toggle?enabled=${enabled}`, {}, { headers: { 'X-Operator': operator } }).then(r => r.data as AlarmRule),
  listAudit: (ruleId?: number) =>
    http.get<AuditEntry[]>('/alarm/audit', { params: ruleId ? { rule_id: ruleId } : {} }).then(r => r.data),

  poll: () => http.post<{ readings: any[]; alarms: AlarmRecord[] }>('/modbus/poll').then(r => r.data),
  listAlarms: (params?: Record<string, unknown>) =>
    http.get<AlarmRecord[]>('/alarm/records', { params }).then(r => r.data),
  ackAlarm: (id: number) => http.post(`/alarm/records/${id}/ack`).then(r => r.data),
}
