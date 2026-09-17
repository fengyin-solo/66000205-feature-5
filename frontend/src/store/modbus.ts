import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api'
import type {
  Device, Alarm, AlarmRecord, FieldError, RuleAudit, ThresholdRule, ThresholdRuleForm
} from '../types'

export const useModbusStore = defineStore('modbus', () => {
  const devices = ref<Device[]>([])
  const alarms = ref<Alarm[]>([])
  const historyData = ref<Record<string, { time: number[]; values: number[] }>>({})
  const isPolling = ref(false)
  const pollInterval = ref(1000)
  const selectedDevice = ref<Device | null>(null)

  // 阈值规则 / 告警记录 / 变更审计（后端持久化）
  const rules = ref<ThresholdRule[]>([])
  const alarmRecords = ref<AlarmRecord[]>([])
  const ruleAudits = ref<RuleAudit[]>([])
  const operator = ref(localStorage.getItem('operator') || 'admin')

  const criticalAlarms = computed(() => alarms.value.filter(a => a.level === 'critical' && !a.acknowledged))
  const onlineDevices = computed(() => devices.value.filter(d => d.online))

  function setOperator(name: string) {
    operator.value = name.trim() || 'admin'
    localStorage.setItem('operator', operator.value)
  }

  function initMockDevices() {
    devices.value = [
      {
        id: 'dev1', name: '温湿度传感器-A区', ip: '192.168.1.101', port: 502, slaveId: 1, online: true,
        registers: [
          { address: 0, name: '温度', type: 'holding', value: 25.6, unit: '°C', updatedAt: Date.now() },
          { address: 1, name: '湿度', type: 'holding', value: 62.3, unit: '%RH', updatedAt: Date.now() },
          { address: 2, name: '露点', type: 'holding', value: 17.8, unit: '°C', updatedAt: Date.now() },
        ]
      },
      {
        id: 'dev2', name: '压力变送器-B区', ip: '192.168.1.102', port: 502, slaveId: 2, online: true,
        registers: [
          { address: 0, name: '管道压力', type: 'holding', value: 3.45, unit: 'MPa', updatedAt: Date.now() },
          { address: 1, name: '差压', type: 'holding', value: 0.12, unit: 'kPa', updatedAt: Date.now() },
        ]
      },
      {
        id: 'dev3', name: '电机控制器-C区', ip: '192.168.1.103', port: 502, slaveId: 3, online: false,
        registers: [
          { address: 0, name: '转速', type: 'holding', value: 1480, unit: 'RPM', updatedAt: Date.now() },
          { address: 1, name: '电流', type: 'holding', value: 12.5, unit: 'A', updatedAt: Date.now() },
          { address: 2, name: '运行状态', type: 'coil', value: true, unit: '', updatedAt: Date.now() },
        ]
      },
      {
        id: 'dev4', name: '流量计-D区', ip: '192.168.1.104', port: 502, slaveId: 4, online: true,
        registers: [
          { address: 0, name: '瞬时流量', type: 'holding', value: 156.7, unit: 'L/min', updatedAt: Date.now() },
          { address: 1, name: '累计流量', type: 'holding', value: 98234, unit: 'L', updatedAt: Date.now() },
        ]
      },
    ]
    selectedDevice.value = devices.value[0]
  }

  // ---------------------------------------------------------------- 阈值规则

  async function fetchRules() {
    const { data } = await api.get('/threshold-rules')
    rules.value = data.rules
  }

  /** 保存规则（新增或修改）。新增时由调用方传入稳定的 clientRequestId 保证重试幂等。 */
  async function saveRule(
    form: ThresholdRuleForm,
    editingId: string | null,
    clientRequestId: string | null
  ): Promise<{ ok: boolean; errors: FieldError[]; message: string }> {
    try {
      const payload: Record<string, unknown> = { ...form, operator: operator.value }
      if (editingId) {
        await api.put(`/threshold-rules/${editingId}`, payload)
      } else {
        await api.post('/threshold-rules', { ...payload, clientRequestId })
      }
      await fetchRules()
      return { ok: true, errors: [], message: '' }
    } catch (e: any) {
      const resp = e?.response
      if (resp?.status === 422 && Array.isArray(resp.data?.errors)) {
        return { ok: false, errors: resp.data.errors, message: resp.data.detail || '规则校验未通过' }
      }
      if (resp?.status === 409) {
        return { ok: false, errors: [], message: resp.data?.detail || '规则已存在' }
      }
      // 网络/服务异常：调用方保持 clientRequestId 不变，重试不会产生重复设置
      return { ok: false, errors: [], message: resp?.data?.detail || '保存失败，请重试' }
    }
  }

  async function deleteRule(id: string) {
    await api.delete(`/threshold-rules/${id}`, { params: { operator: operator.value } })
    await fetchRules()
  }

  async function toggleRule(rule: ThresholdRule) {
    await saveRule({ ...rule, enabled: !rule.enabled, operator: operator.value }, rule.id, null)
  }

  // ---------------------------------------------------------------- 告警判定与记录

  /** 把本轮采集读数提交给后端判定引擎，命中当前生效规则则生成告警记录 */
  async function evaluateReadings() {
    const readings: Record<string, unknown>[] = []
    for (const dev of devices.value) {
      if (!dev.online) continue
      for (const reg of dev.registers) {
        if (typeof reg.value !== 'number') continue
        readings.push({
          deviceId: dev.id, deviceName: dev.name,
          registerAddress: reg.address, registerName: reg.name,
          value: reg.value, unit: reg.unit,
        })
      }
    }
    if (!readings.length) return
    try {
      const { data } = await api.post('/alarm-engine/evaluate', { readings })
      for (const rec of data.alarms as AlarmRecord[]) {
        alarms.value.unshift(recordToAlarm(rec))
      }
      if (alarms.value.length > 50) alarms.value = alarms.value.slice(0, 50)
    } catch (e) {
      console.warn('告警判定服务暂不可用', e)
    }
  }

  function recordToAlarm(rec: AlarmRecord): Alarm {
    return {
      id: rec.id, deviceId: rec.deviceId, register: rec.registerName,
      message: rec.message, level: rec.level,
      timestamp: rec.createdAt, acknowledged: rec.acknowledged,
    }
  }

  async function fetchAlarmRecords(limit = 100) {
    const { data } = await api.get('/alarms', { params: { limit } })
    alarmRecords.value = data.alarms
  }

  /** 大屏告警列表从后端记录水合，刷新后展示一致 */
  async function hydrateAlarms() {
    try {
      const { data } = await api.get('/alarms', { params: { limit: 10 } })
      alarms.value = (data.alarms as AlarmRecord[]).map(recordToAlarm)
    } catch (e) {
      console.warn('告警记录加载失败', e)
    }
  }

  async function acknowledgeAlarm(id: string) {
    const a = alarms.value.find(a => a.id === id)
    if (a) a.acknowledged = true
    try {
      await api.post(`/alarms/${id}/ack`)
    } catch (e) {
      console.warn('告警确认失败', e)
    }
  }

  async function acknowledgeRecord(id: string) {
    await api.post(`/alarms/${id}/ack`)
    const rec = alarmRecords.value.find(r => r.id === id)
    if (rec) rec.acknowledged = true
    const a = alarms.value.find(a => a.id === id)
    if (a) a.acknowledged = true
  }

  // ---------------------------------------------------------------- 变更审计

  async function fetchAudits(limit = 200) {
    const { data } = await api.get('/threshold-rule-audits', { params: { limit } })
    ruleAudits.value = data.audits
  }

  // ---------------------------------------------------------------- 采集模拟

  function simulatePoll() {
    for (const dev of devices.value) {
      if (!dev.online) continue
      for (const reg of dev.registers) {
        if (typeof reg.value === 'number') {
          const noise = (Math.random() - 0.5) * reg.value * 0.02
          reg.value = Math.round((reg.value + noise) * 100) / 100
          reg.updatedAt = Date.now()
          const key = `${dev.id}_${reg.address}`
          if (!historyData.value[key]) historyData.value[key] = { time: [], values: [] }
          historyData.value[key].time.push(Date.now())
          historyData.value[key].values.push(reg.value)
          if (historyData.value[key].time.length > 100) {
            historyData.value[key].time.shift()
            historyData.value[key].values.shift()
          }
        }
      }
    }
    // 越限判定交给后端按当前生效规则执行（异步，不阻塞采集）
    evaluateReadings()
  }

  function toggleDevice(id: string) {
    const d = devices.value.find(d => d.id === id)
    if (d) d.online = !d.online
  }

  return {
    devices, alarms, historyData, isPolling, pollInterval, selectedDevice,
    rules, alarmRecords, ruleAudits, operator,
    criticalAlarms, onlineDevices,
    initMockDevices, simulatePoll, acknowledgeAlarm, toggleDevice,
    setOperator, fetchRules, saveRule, deleteRule, toggleRule,
    fetchAlarmRecords, hydrateAlarms, acknowledgeRecord, fetchAudits,
  }
})
