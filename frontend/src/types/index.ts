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

export interface Alarm {
  id: string
  deviceId: string
  register: string
  message: string
  level: 'info' | 'warning' | 'critical'
  timestamp: number
  acknowledged: boolean
}

export type AlarmLevel = 'info' | 'warning' | 'critical'
export type ThresholdCondition = 'above_upper' | 'below_lower' | 'out_of_range' | 'in_range'

/** 阈值规则：deviceId 为 '*' 时表示对全部设备生效 */
export interface ThresholdRule {
  id: string
  deviceId: string
  registerAddress: number
  registerName: string
  lowerLimit: number | null
  upperLimit: number | null
  condition: ThresholdCondition
  level: AlarmLevel
  enabled: boolean
  createdBy: string
  createdAt: number
  updatedBy: string | null
  updatedAt: number | null
}

/** 规则表单（新增/编辑共用） */
export interface ThresholdRuleForm {
  deviceId: string
  registerAddress: number
  registerName: string
  lowerLimit: number | null
  upperLimit: number | null
  condition: ThresholdCondition
  level: AlarmLevel
  enabled: boolean
  operator: string
}

export interface FieldError {
  field: string
  message: string
}

/** 规则变更审计记录 */
export interface RuleAudit {
  id: number
  ruleId: string
  action: 'create' | 'update' | 'delete'
  operator: string
  changedFields: string[]
  before: Partial<ThresholdRule> | null
  after: Partial<ThresholdRule> | null
  createdAt: number
}

/** 告警记录（后端持久化，等级为产生时的快照） */
export interface AlarmRecord {
  id: string
  ruleId: string | null
  deviceId: string
  deviceName: string
  registerAddress: number
  registerName: string
  value: number
  unit: string
  level: AlarmLevel
  message: string
  acknowledged: boolean
  createdAt: number
}
