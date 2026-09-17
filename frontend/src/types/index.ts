export interface ModbusRegister {
  address: number
  name: string
  type: 'coil' | 'discrete' | 'holding' | 'input'
  value: number | boolean
  unit: string
  updatedAt: number
}

export interface Device {
  id: string
  name: string
  ip: string
  port: number
  slaveId: number
  online: boolean
  registers: ModbusRegister[]
}

export type AlarmLevel = 'info' | 'warning' | 'critical'
export type AlarmCondition = 'gt' | 'lt' | 'between' | 'outside'

/** Server-side alarm rule, per point. */
export interface AlarmRule {
  id: number
  point: string
  condition: AlarmCondition
  upperLimit: number | null
  lowerLimit: number | null
  level: AlarmLevel
  scope: string[]
  enabled: boolean
  version: number
  createdBy: string
  updatedBy: string
  createdAt: string
  updatedAt: string
}

export interface RulePayload {
  point: string
  condition: AlarmCondition
  upperLimit: number | null
  lowerLimit: number | null
  level: AlarmLevel
  scope: string[]
  enabled: boolean
}

/** Historical alarm — level/ruleVersion are a snapshot taken when raised. */
export interface AlarmRecord {
  id: number
  point: string
  deviceId: string | null
  deviceName: string | null
  value: number
  unit: string
  level: AlarmLevel
  ruleId: number | null
  ruleVersion: number | null
  message: string
  raisedAt: string
  acknowledged: boolean
}

export interface AuditChange { old: unknown; new: unknown }

export interface AuditEntry {
  id: number
  ruleId: number | null
  point: string
  action: 'create' | 'update' | 'enable' | 'disable'
  operator: string
  changedAt: string
  changes: Record<string, AuditChange>
  before: Record<string, unknown> | null
  after: Record<string, unknown> | null
}

export interface RuleMeta {
  conditions: { value: AlarmCondition; label: string }[]
  levels: AlarmLevel[]
  points: string[]
  devices: { id: string; name: string }[]
}

/** Legacy in-memory alarm used by the dashboard sidebar. */
export interface Alarm {
  id: string
  deviceId: string
  register: string
  message: string
  level: AlarmLevel
  timestamp: number
  acknowledged: boolean
}
