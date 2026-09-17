# solo-6600020: Modbus 工业协议数据采集监控大屏

## 技术栈
- Frontend: Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS + ECharts
- Backend: Python FastAPI + pymodbus（判定/规则/记录持久化使用标准库 sqlite3，零额外依赖）

## 核心特性
1. **Modbus RTU/TCP 寄存器实时读取**：pymodbus 连接工业设备
2. **时序曲线 ECharts 绘制**：实时趋势图，多寄存器对比
3. **阈值告警 WebSocket 推送**：温度/压力超限自动告警
4. **设备拓扑 SVG 图**：可视化设备布局与在线状态
5. **采集任务调度**：可调轮询间隔，设备启停控制
6. **可配置的点位越限规则**（新增）：
   - 每个点位可独立配置上限/下限、判定条件（高于上限 / 低于下限 / 超出区间 / 落入禁区）、
     提醒等级（info / warning / critical）与生效设备范围（空 = 全部设备）
   - 保存前逐字段校验（阈值缺失、下限 ≥ 上限、范围含不存在的设备、重复规则等），
     不通过返回 400 与字段级错误信息，**不写入任何内容**
   - 判定引擎每次采集读取最新规则，保存后**下一周期立即按新口径生效**
   - 告警产生时把等级与规则版本作为**快照**写入记录；之后再改规则，历史记录仍按当时等级展示，刷新不变
   - 所有新增/修改/启停写入审计日志（操作人、时间、逐字段新旧值，可按规则回看）
   - 保存接口支持 `Idempotency-Key`：同一请求（含网络失败后的重试）只会产生一条规则与一条留痕

## 启动
```bash
cd frontend && npm install && npm run dev
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8002
```
首次启动自动在 `backend/data/app.db` 建库（可用环境变量 `ALARM_DB_DIR` 改位置）。

## 主要接口
- `GET  /api/alarm/meta`            点位 / 设备 / 条件 / 等级可选项
- `GET  /api/alarm/rules`           规则列表
- `POST /api/alarm/rules`           新增（Header: `X-Operator`、`Idempotency-Key`）
- `PUT  /api/alarm/rules/{id}`      修改（同上，规则版本号 +1）
- `POST /api/alarm/rules/{id}/toggle?enabled=` 启停
- `GET  /api/alarm/audit[?rule_id=]` 变更留痕
- `POST /api/modbus/poll`           一轮采集 + 按当前规则判定，返回新告警（含快照）
- `GET  /api/alarm/records`         历史告警（等级为触发时快照，支持点位/设备/等级/确认状态过滤）

## 测试
```bash
cd backend && python3 tests/test_alarm_rules.py
```
覆盖：各类校验失败、重复规则拦截、幂等重试（只产生一条设置/一条留痕）、
规则即时生效、历史等级快照不随修改/刷新变化、生效范围隔离、审计留痕。
