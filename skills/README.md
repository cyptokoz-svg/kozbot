# JARVIS 记忆与通知系统

## 🎯 功能概览

- **三层记忆防护**: 紧急缓存 → 每日日志 → 长期记忆
- **智能通知**: 4级优先级 + 时间感知 + 批量汇总
- **零重复**: 自动去重 + 上下文恢复

## 🚀 快速开始

### 1. 会话启动时自动恢复

```bash
python3 skills/session_startup.py
```

### 2. 在代码中集成

```python
from skills.memory_notification_system import MemoryGuard, SmartNotifier, Priority

# 初始化
memory = MemoryGuard()
notifier = SmartNotifier(memory)

# 上下文压缩前保护
memory.emergency_save(
    content="重要决策内容",
    tags=["CRITICAL", "DECISION"]
)

# 发送智能通知
notifier.notify(
    title="交易信号",
    content="UP 信号触发",
    priority=Priority.HIGH,
    tags=["TRADING"]
)
```

## 📁 文件结构

```
skills/
├── memory_notification_system.py  # 核心系统
├── session_startup.py              # 会话启动恢复
├── usage_example.py                # 使用示例
└── README.md                       # 本文档
```

## 🧠 记忆三层架构

| 层级 | 位置 | 用途 | 保留时间 |
|------|------|------|----------|
| 🔴 Layer 1 | `/tmp/jarvis_session_cache.json` | 紧急缓存，压缩前自动保存 | 直到恢复 |
| 🟡 Layer 2 | `memory/YYYY-MM-DD.md` | 每日详细日志 | 永久 |
| 🟢 Layer 3 | `MEMORY.md` | 长期核心记忆 | 永久 |

## 🔔 通知优先级

| 优先级 | 图标 | 触发条件 | 通知方式 |
|--------|------|----------|----------|
| 🔴 CRITICAL | 紧急 | 资金风险、系统崩溃 | 立即 + 重复提醒 |
| 🟠 HIGH | 重要 | 交易信号、Sir @我 | 立即 |
| 🟡 MEDIUM | 一般 | 新回复、截止<1h | 智能窗口 |
| 🟢 LOW | 低优 | 日常统计 | 批量汇总 |

## ⏰ 时间感知

- **深夜 (23:00-08:00)**: 仅紧急通知
- **工作时间 (09:00-18:00)**: 紧急+重要
- **晚间 (19:00-22:00)**: 全部通知

## 🏷️ 自动标签

- `[CRITICAL]`: 必须保留
- `[TODO]`: 待办任务
- `[DECISION]`: 重要决策
- `[REFERENCE]`: 参考资料

## 📊 使用示例

见 `skills/usage_example.py`

## 🔧 集成到主系统

在交易机器人等主流程中添加:

```python
from skills.memory_notification_system import MemoryGuard, SmartNotifier, Priority

class TradingBot:
    def __init__(self):
        self.memory = MemoryGuard()
        self.notifier = SmartNotifier(self.memory)
    
    def before_context_compression(self):
        """压缩前自动保存"""
        self.memory.emergency_save(
            content=self.get_current_context(),
            tags=["TRADING", "SESSION_BACKUP"]
        )
    
    def on_trade_signal(self, signal):
        """交易信号触发"""
        self.notifier.notify(
            title=f"📊 交易信号 | {signal.direction}",
            content=f"Edge: {signal.edge:+.1%}",
            priority=Priority.HIGH if abs(signal.edge) > 0.15 else Priority.MEDIUM
        )
```

## 📝 版本记录

- v1.0.0 (2026-01-30): 初始版本，三层记忆 + 智能通知
