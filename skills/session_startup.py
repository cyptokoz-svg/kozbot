#!/usr/bin/env python3
"""
JARVIS Session Manager
会话启动时自动恢复记忆 + 初始化通知系统
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_notification_system import MemoryGuard, SmartNotifier, Priority

def main():
    print("🧠 JARVIS 记忆与通知系统启动...")
    
    # 初始化
    memory = MemoryGuard()
    notifier = SmartNotifier(memory)
    
    # 1. 会话恢复检查
    print("\n1️⃣ 检查会话恢复...")
    recovery = memory.session_recovery()
    
    if recovery["events"]:
        print(f"   从压缩中恢复 {len(recovery['events'])} 个事件")
        for event in recovery["events"][:3]:
            print(f"   - [{', '.join(event['tags'])}] {event['content'][:50]}...")
    else:
        print("   无需恢复")
    
    # 2. 发送恢复通知
    print("\n2️⃣ 发送恢复通知...")
    notifier.check_and_notify_recovery()
    
    # 3. 系统就绪通知
    print("\n3️⃣ 系统就绪...")
    notifier.notify(
        title="🦞 JARVIS 在线",
        content="记忆防护系统已激活 | 智能通知已启用 | 等待您的指令",
        priority=Priority.LOW,
        tags=["SYSTEM"]
    )
    
    print("\n✅ 系统启动完成")

if __name__ == "__main__":
    main()
