#!/usr/bin/env python3
"""
JARVIS Memory & Notification System
三层记忆防护 + 智能通知
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class Priority(Enum):
    CRITICAL = "🔴"  # 资金风险、系统崩溃
    HIGH = "🟠"      # 交易信号、Sir @我
    MEDIUM = "🟡"    # 新回复、截止<1h
    LOW = "🟢"       # 日常统计、汇总

@dataclass
class MemoryEvent:
    """记忆事件"""
    timestamp: str
    content: str
    tags: List[str]  # [CRITICAL, TODO, DECISION, REFERENCE]
    source: str
    
@dataclass
class Notification:
    """通知对象"""
    id: str
    priority: Priority
    title: str
    content: str
    created_at: str
    delivered: bool = False
    context: Optional[Dict] = None

class MemoryGuard:
    """三层记忆防护系统"""
    
    def __init__(self, base_path: str = "/home/ubuntu/clawd"):
        self.base_path = base_path
        self.layer1_path = "/tmp/jarvis_session_cache.json"
        self.layer2_dir = os.path.join(base_path, "memory")
        self.layer3_path = os.path.join(base_path, "MEMORY.md")
        
        os.makedirs(self.layer2_dir, exist_ok=True)
        self._ensure_layer1_exists()
    
    def _ensure_layer1_exists(self):
        """确保紧急缓存存在"""
        if not os.path.exists(self.layer1_path):
            self._save_layer1({"events": [], "last_updated": datetime.now(timezone.utc).isoformat()})
    
    def _save_layer1(self, data: Dict):
        """保存到紧急缓存"""
        with open(self.layer1_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_layer1(self) -> Dict:
        """读取紧急缓存"""
        try:
            with open(self.layer1_path, 'r') as f:
                return json.load(f)
        except:
            return {"events": [], "last_updated": datetime.now(timezone.utc).isoformat()}
    
    def emergency_save(self, content: str, tags: List[str], source: str = "auto"):
        """
        紧急保存 - Layer 1
        在上下文压缩前自动调用
        """
        event = MemoryEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            content=content,
            tags=tags,
            source=source
        )
        
        data = self._load_layer1()
        data["events"].append(asdict(event))
        data["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._save_layer1(data)
        
        # 同时追加到每日日志
        self._append_to_daily(event)
        
        return event
    
    def _append_to_daily(self, event: MemoryEvent):
        """追加到每日日志 - Layer 2"""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily_path = os.path.join(self.layer2_dir, f"{today}.md")
        
        tag_str = ", ".join(event.tags)
        entry = f"""
## {event.timestamp}
**Tags:** {tag_str} | **Source:** {event.source}

{event.content}

---
"""
        with open(daily_path, 'a', encoding='utf-8') as f:
            f.write(entry)
    
    def session_recovery(self) -> List[Dict]:
        """
        会话恢复
        新会话开始时调用，返回未处理的事件
        """
        data = self._load_layer1()
        events = data.get("events", [])
        
        # 筛选未完成的任务
        todo_events = [e for e in events if "TODO" in e.get("tags", [])]
        critical_events = [e for e in events if "CRITICAL" in e.get("tags", [])]
        
        # 清空 Layer 1 (已恢复)
        if events:
            self._save_layer1({"events": [], "last_updated": datetime.now(timezone.utc).isoformat()})
        
        return {
            "todo_count": len(todo_events),
            "critical_count": len(critical_events),
            "events": todo_events + critical_events
        }
    
    def archive_to_longterm(self, event_content: str, category: str):
        """
        归档到长期记忆 - Layer 3
        手动调用，将重要决策/教训写入 MEMORY.md
        """
        entry = f"""
## {datetime.now(timezone.utc).strftime('%Y-%m-%d')} - {category}

{event_content}
"""
        with open(self.layer3_path, 'a', encoding='utf-8') as f:
            f.write(entry)


class SmartNotifier:
    """智能通知系统"""
    
    def __init__(self, memory_guard: MemoryGuard):
        self.memory = memory_guard
        self.queue = []  # 待发送队列
        self.last_notified = {}  # 去重记录 {hash: timestamp}
        self.dedup_window = 3600  # 1小时内不重复通知
        
    def _get_current_hour(self) -> int:
        """获取用户本地时间 (假设 UTC+8)"""
        return (datetime.now(timezone.utc).hour + 8) % 24
    
    def _should_notify_now(self, priority: Priority) -> bool:
        """判断是否应该立即通知"""
        hour = self._get_current_hour()
        
        # 深夜模式 (23:00-08:00)
        if 23 <= hour or hour < 8:
            return priority == Priority.CRITICAL
        
        # 工作时间 (09:00-18:00)
        if 9 <= hour < 18:
            return priority in [Priority.CRITICAL, Priority.HIGH]
        
        # 晚间 (19:00-22:00)
        return True
    
    def _is_duplicate(self, content: str) -> bool:
        """检查是否重复通知"""
        content_hash = hash(content) % 1000000
        now = time.time()
        
        if content_hash in self.last_notified:
            if now - self.last_notified[content_hash] < self.dedup_window:
                return True
        
        self.last_notified[content_hash] = now
        return False
    
    def notify(self, title: str, content: str, priority: Priority, 
               tags: List[str] = None, context: Dict = None):
        """
        发送智能通知
        
        Args:
            title: 通知标题
            content: 通知内容
            priority: 优先级
            tags: 记忆标签 (自动保存到记忆系统)
            context: 额外上下文
        """
        # 去重检查
        if self._is_duplicate(title + content[:50]):
            return None
        
        # 保存到记忆系统
        if tags:
            self.memory.emergency_save(
                content=f"{title}: {content}",
                tags=tags,
                source="notification"
            )
        
        # 判断是否立即发送
        if self._should_notify_now(priority):
            return self._send_immediate(title, content, priority, context)
        else:
            # 加入队列，稍后批量发送
            self._queue_notification(title, content, priority)
            return None
    
    def _send_immediate(self, title: str, content: str, 
                        priority: Priority, context: Dict = None) -> Notification:
        """立即发送通知"""
        notif = Notification(
            id=f"notif_{int(time.time())}_{hash(content) % 10000}",
            priority=priority,
            title=title,
            content=content,
            created_at=datetime.now(timezone.utc).isoformat(),
            context=context
        )
        
        # 这里调用实际的 Telegram 发送
        self._telegram_send(notif)
        notif.delivered = True
        
        return notif
    
    def _queue_notification(self, title: str, content: str, priority: Priority):
        """加入待发送队列"""
        self.queue.append({
            "title": title,
            "content": content,
            "priority": priority,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    def _telegram_send(self, notif: Notification):
        """发送 Telegram 消息 (占位，实际集成 clawdbot)"""
        emoji = notif.priority.value
        message = f"""
{emoji} {notif.title}

{notif.content}
"""
        # 实际实现: 调用 clawdbot message send
        print(f"[TELEGRAM] {message[:200]}...")
    
    def send_batch_summary(self):
        """发送批量汇总 (低优先级通知)"""
        if not self.queue:
            return
        
        # 按优先级分组
        medium_items = [n for n in self.queue if n["priority"] == Priority.MEDIUM]
        low_items = [n for n in self.queue if n["priority"] == Priority.LOW]
        
        summary_parts = []
        
        if medium_items:
            summary_parts.append(f"🟡 待处理事项: {len(medium_items)} 项")
            for item in medium_items[:3]:
                summary_parts.append(f"  • {item['title']}")
        
        if low_items:
            summary_parts.append(f"🟢 日常动态: {len(low_items)} 项")
        
        if summary_parts:
            summary = "\n".join(summary_parts)
            self._send_immediate(
                title="📋 通知汇总",
                content=summary,
                priority=Priority.LOW
            )
        
        # 清空队列
        self.queue = []
    
    def check_and_notify_recovery(self):
        """检查并通知会话恢复"""
        recovery = self.memory.session_recovery()
        
        if recovery["critical_count"] > 0:
            self.notify(
                title="🧠 会话恢复",
                content=f"检测到 {recovery['critical_count']} 项紧急事项从压缩中恢复",
                priority=Priority.HIGH,
                tags=["CRITICAL"]
            )
        
        if recovery["todo_count"] > 0:
            self.notify(
                title="✅ 待办提醒",
                content=f"您有 {recovery['todo_count']} 个未完成任务",
                priority=Priority.MEDIUM,
                tags=["TODO"]
            )


# 使用示例
if __name__ == "__main__":
    # 初始化
    memory = MemoryGuard()
    notifier = SmartNotifier(memory)
    
    # 示例1: 交易信号 (高优先级)
    notifier.notify(
        title="📊 交易信号触发",
        content="UP 信号 | Edge: +18.3% | 建议关注",
        priority=Priority.HIGH,
        tags=["DECISION", "TRADING"]
    )
    
    # 示例2: Moltbook 回复 (中优先级，进入队列)
    notifier.notify(
        title="💬 Moltbook 新回复",
        content="alfred_bat 回复了您的帖子",
        priority=Priority.MEDIUM,
        tags=["SOCIAL"]
    )
    
    # 示例3: 发送批量汇总
    notifier.send_batch_summary()
    
    # 示例4: 会话恢复检查
    notifier.check_and_notify_recovery()
