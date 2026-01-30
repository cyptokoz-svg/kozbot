#!/usr/bin/env python3
"""
JARVIS 记忆-通知系统使用示例
演示如何在实际代码中集成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_notification_system import MemoryGuard, SmartNotifier, Priority

class JARVISCore:
    """集成记忆和通知的 JARVIS 核心"""
    
    def __init__(self):
        self.memory = MemoryGuard()
        self.notifier = SmartNotifier(self.memory)
        self.context_threshold = 0.7  # 70% 容量时触发保护
        
    # ========== 记忆保护接口 ==========
    
    def before_compression(self, critical_info: str):
        """
        上下文压缩前调用
        自动保存关键信息
        """
        self.memory.emergency_save(
            content=critical_info,
            tags=["CRITICAL", "SESSION_BACKUP"],
            source="pre_compression"
        )
        print(f"[记忆保护] 已保存 {len(critical_info)} 字符到紧急缓存")
    
    def mark_todo(self, task: str):
        """标记待办事项"""
        self.memory.emergency_save(
            content=task,
            tags=["TODO", "PENDING"],
            source="user_request"
        )
        self.notifier.notify(
            title="✅ 待办已记录",
            content=task,
            priority=Priority.LOW,
            tags=["TODO"]
        )
    
    def record_decision(self, decision: str, rationale: str = ""):
        """记录重要决策"""
        content = f"决策: {decision}\n理由: {rationale}"
        self.memory.emergency_save(
            content=content,
            tags=["DECISION", "CRITICAL"],
            source="decision_making"
        )
        self.memory.archive_to_longterm(content, category="Decisions")
    
    # ========== 智能通知接口 ==========
    
    def notify_trade_signal(self, direction: str, edge: float, action: str):
        """交易信号通知"""
        priority = Priority.HIGH if abs(edge) > 0.15 else Priority.MEDIUM
        
        self.notifier.notify(
            title=f"📊 交易信号 | {direction}",
            content=f"Edge: {edge:+.1%}\n建议: {action}",
            priority=priority,
            tags=["TRADING", "DECISION"],
            context={"direction": direction, "edge": edge}
        )
    
    def notify_moltbook_reply(self, author: str, post_title: str):
        """Moltbook 回复通知"""
        # 高 Karma 作者立即通知，其他批量处理
        high_karma_authors = ["eudaemon_0", "Ronin", "Fred", "bicep"]
        priority = Priority.MEDIUM if author in high_karma_authors else Priority.LOW
        
        self.notifier.notify(
            title=f"💬 {author} 回复了您",
            content=f"帖子: {post_title[:40]}...",
            priority=priority,
            tags=["SOCIAL", "MOLTBOOK"]
        )
    
    def notify_system_alert(self, alert_type: str, message: str):
        """系统警报"""
        priority = Priority.CRITICAL if "error" in alert_type.lower() else Priority.HIGH
        
        self.notifier.notify(
            title=f"🚨 {alert_type}",
            content=message,
            priority=priority,
            tags=["SYSTEM", "ALERT"]
        )
    
    def daily_summary(self):
        """发送每日汇总"""
        self.notifier.send_batch_summary()


# ========== 使用示例 ==========

if __name__ == "__main__":
    jarvis = JARVISCore()
    
    print("=" * 50)
    print("示例1: 上下文压缩保护")
    print("=" * 50)
    jarvis.before_compression("重要讨论: 今晚需要决定 Edge 阈值调整方案")
    jarvis.mark_todo("回复 XiaoZhuang 的记忆管理讨论")
    
    print("\n" + "=" * 50)
    print("示例2: 交易信号通知")
    print("=" * 50)
    jarvis.notify_trade_signal("UP", 0.183, "信号强劲，建议关注")
    
    print("\n" + "=" * 50)
    print("示例3: Moltbook 社交通知")
    print("=" * 50)
    jarvis.notify_moltbook_reply("Ronin", "Nightly Build Review")
    jarvis.notify_moltbook_reply("random_user", "Some post")
    
    print("\n" + "=" * 50)
    print("示例4: 系统警报")
    print("=" * 50)
    jarvis.notify_system_alert("Edge 截断保护", "检测到 -72% 极端信号，已截断至 -50%")
    
    print("\n" + "=" * 50)
    print("示例5: 每日汇总")
    print("=" * 50)
    jarvis.daily_summary()
    
    print("\n✅ 所有示例执行完成")
