# solo-6600020: Modbus 工业协议数据采集监控大屏

## 技术栈
- Frontend: Vue 3 + TypeScript + Vite + Pinia + Tailwind CSS + ECharts
- Backend: Python FastAPI + pymodbus

## 核心特性
1. **Modbus RTU/TCP 寄存器实时读取**：pymodbus 连接工业设备
2. **时序曲线 ECharts 绘制**：实时趋势图，多寄存器对比
3. **可配置阈值告警**：每个点位可独立配置上下限、判定条件（高于上限/低于下限/超出范围/范围内）与提醒等级（提示/警告/严重），保存前服务端逐项校验，调整后立即按新口径判定
4. **告警记录持久化**：记录按产生时的等级快照留存（SQLite），多入口查看、刷新均不受影响
5. **变更审计**：规则的新增/修改/删除全部留痕，谁在什么时候改了哪一项均可回看；保存幂等，失败重试不产生重复设置
6. **设备拓扑 SVG 图**：可视化设备布局与在线状态
7. **采集任务调度**：可调轮询间隔，设备启停控制

## 启动
```bash
cd frontend && npm install && npm run dev
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload --port 8002
```
