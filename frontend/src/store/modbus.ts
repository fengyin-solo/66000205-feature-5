import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { Device, Alarm, AlarmRecord } from '../types'
import { api } from '../api'

/**
 * Acquisition store. Each poll cycle asks the backend to evaluate readings
 * against the *current* rule set, so a rule change takes effect on the next
 * cycle. Sidebar alarms are a transient copy; the persisted snapshot records
 * live in the alarm-records view.
 */
export const useModbusStore = defineStore('modbus', () => {
  const devices = ref<Device[]>([])
  const alarms = ref<Alarm[]>([])
  const historyData = ref<Record<string, { time: number[]; values: number[] }>>({})
  const isPolling = ref(false)
  const pollInterval = ref(1000)
  const selectedDevice = ref<Device | null>(null)
  const backendOnline = ref(false)

  const criticalAlarms = computed(() => alarms.value.filter(a => a.level === 'critical' && !a.acknowledged))
  const onlineDevices = computed(() => devices.value.filter(d => d.online))

  const DEVICE_INDEX: Record<string, { name: string; ip: string; port: number; slaveId: number; registers: { address: number; name: string; type: 'holding'; unit: string }[] }> = {
    dev1: { name: '温湿度传感器-A区', ip: '192.168.1.101', port: 502, slaveId: 1, registers: [
      { address: 0, name: '温度', type: 'holding', unit: '°C' },
      { address: 1, name: '湿度', type: 'holding', unit: '%RH' },
      { address: 2, name: '露点', type: 'holding', unit: '°C' },
    ]},
    dev2: { name: '压力变送器-B区', ip: '192.168.1.102', port: 502, slaveId: 2, registers: [
      { address: 0, name: '管道压力', type: 'holding', unit: 'MPa' },
      { address: 1, name: '差压', type: 'holding', unit: 'kPa' },
    ]},
    dev3: { name: '电机控制器-C区', ip: '192.168.1.103', port: 502, slaveId: 3, registers: [
      { address: 0, name: '转速', type: 'holding', unit: 'RPM' },
      { address: 1, name: '电流', type: 'holding', unit: 'A' },
    ]},
    dev4: { name: '流量计-D区', ip: '192.168.1.104', port: 502, slaveId: 4, registers: [
      { address: 0, name: '瞬时流量', type: 'holding', unit: 'L/min' },
      { address: 1, name: '累计流量', type: 'holding', unit: 'L' },
    ]},
  }

  function initMockDevices(onlineIds: string[] = ['dev1', 'dev2', 'dev4']) {
    devices.value = Object.entries(DEVICE_INDEX).map(([id, d]) => ({
      id, name: d.name, ip: d.ip, port: d.port, slaveId: d.slaveId,
      online: onlineIds.includes(id),
      registers: d.registers.map(r => ({ ...r, value: 0, updatedAt: Date.now() })),
    }))
    if (!selectedDevice.value) selectedDevice.value = devices.value[0]
  }

  function ingest(readings: { deviceId: string; address: number; point: string; unit: string; value: number }[], newAlarms: AlarmRecord[]) {
    for (const rd of readings) {
      const dev = devices.value.find(d => d.id === rd.deviceId)
      const reg = dev?.registers.find(r => r.address === rd.address)
      if (!dev || !reg) continue
      reg.value = rd.value
      reg.updatedAt = Date.now()
      const key = `${rd.deviceId}_${rd.address}`
      if (!historyData.value[key]) historyData.value[key] = { time: [], values: [] }
      historyData.value[key].time.push(Date.now())
      historyData.value[key].values.push(rd.value)
      if (historyData.value[key].time.length > 100) {
        historyData.value[key].time.shift()
        historyData.value[key].values.shift()
      }
    }
    for (const a of newAlarms) {
      alarms.value.unshift({
        id: `srv_${a.id}`, deviceId: a.deviceId ?? '', register: a.point,
        message: a.message, level: a.level, timestamp: Date.parse(a.raisedAt), acknowledged: false,
      })
    }
    if (alarms.value.length > 50) alarms.value = alarms.value.slice(0, 50)
  }

  async function pollOnce() {
    try {
      const res = await api.poll()
      backendOnline.value = true
      ingest(res.readings, res.alarms)
    } catch {
      backendOnline.value = false
    }
  }

  function acknowledgeAlarm(id: string) {
    const a = alarms.value.find(a => a.id === id)
    if (a) a.acknowledged = true
    const serverId = id.startsWith('srv_') ? Number(id.slice(4)) : NaN
    if (Number.isFinite(serverId)) api.ackAlarm(serverId).catch(() => {})
  }

  function toggleDevice(id: string) {
    const d = devices.value.find(d => d.id === id)
    if (d) d.online = !d.online
  }

  return {
    devices, alarms, historyData, isPolling, pollInterval, selectedDevice, backendOnline,
    criticalAlarms, onlineDevices,
    initMockDevices, ingest, pollOnce, acknowledgeAlarm, toggleDevice,
  }
})
