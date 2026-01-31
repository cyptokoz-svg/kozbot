#!/usr/bin/env python3
"""
Hyperliquid Funding Rate 监控示例
演示如何使用 freqtrade-hyperliquid Skill
"""

import asyncio
import os
import sys

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'freqtrade_hl'))

from freqtrade_hl import HyperliquidExchange, FundingMonitor, FundingSignalGenerator


async def main():
    """主函数"""
    print("🚀 Hyperliquid Funding Rate Monitor Demo")
    print("=" * 50)
    
    # 创建交易所客户端 (使用测试网)
    exchange = HyperliquidExchange(
        api_key=os.getenv("HYPERLIQUID_API_KEY"),
        api_secret=os.getenv("HYPERLIQUID_SECRET"),
        wallet_address=os.getenv("HYPERLIQUID_WALLET"),
        testnet=True
    )
    
    try:
        # 1. 获取所有资金费率
        print("\n📊 获取所有 Funding Rates...")
        rates = await exchange.get_all_funding_rates()
        print(f"   共 {len(rates)} 个交易对")
        
        # 显示前5个
        for rate in rates[:5]:
            print(f"   {rate.symbol}: {rate.funding_rate:.4%}")
        
        # 2. 获取极端资金费率
        print("\n🚨 检测极端 Funding Rates (|rate| >= 0.1%)...")
        extreme_rates = await exchange.get_extreme_funding_rates(threshold=0.001)
        
        if extreme_rates:
            print(f"   发现 {len(extreme_rates)} 个极端值:")
            for rate in extreme_rates:
                direction = "📈 多付空" if rate.funding_rate > 0 else "📉 空付多"
                print(f"   {rate.symbol}: {rate.funding_rate:.4%} {direction}")
        else:
            print("   暂无极端值")
        
        # 3. 获取套利机会
        print("\n💰 检测套利机会...")
        opportunities = await exchange.get_funding_arbitrage_opportunities()
        
        if opportunities:
            for opp in opportunities[:3]:
                print(f"   {opp['symbol']}: {opp['description']}")
                print(f"   预计年化收益: ${opp['expected_annual_funding']:.2f}")
        else:
            print("   暂无套利机会")
        
        # 4. 启动实时监控 (演示10秒)
        print("\n🔔 启动实时监控 (10秒)...")
        
        def on_extreme_funding(rate, is_extreme):
            """极端 funding 回调函数"""
            if is_extreme:
                print(f"   ⚠️ 检测到极端: {rate.symbol} = {rate.funding_rate:.4%}")
        
        monitor = FundingMonitor(
            exchange=exchange,
            check_interval=5,  # 每5秒检查一次
            extreme_threshold=0.001
        )
        
        # 添加信号生成器
        signal_gen = FundingSignalGenerator(monitor)
        
        # 添加回调
        monitor.add_callback(on_extreme_funding)
        monitor.add_callback(lambda r, e: signal_gen.generate_signal(r) if e else None)
        
        # 启动监控
        await monitor.start_monitoring()
        
        # 运行10秒
        await asyncio.sleep(10)
        
        # 停止监控
        await monitor.stop_monitoring()
        
        # 显示统计
        stats = monitor.get_current_stats()
        print(f"\n📈 监控统计:")
        print(f"   检查对数: {stats.get('total_pairs', 0)}")
        print(f"   极端次数: {stats.get('extreme_count', 0)}")
        
        # 显示生成的信号
        signals = signal_gen.get_recent_signals(n=5)
        if signals:
            print(f"\n📡 生成的交易信号:")
            for sig in signals:
                print(f"   {sig['symbol']}: {sig['direction']}")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await exchange.close()
        print("\n✅ 演示完成")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())
