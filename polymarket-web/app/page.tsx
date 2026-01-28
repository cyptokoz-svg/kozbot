import StatCard from "../components/StatCard";
import PnLChart from "../components/PnLChart";

// Mock Data (In real version, fetch this from GitHub Raw JSON)
const MOCK_DATA = {
  winRate: "63.6%",
  profitFactor: "2.33",
  netPnL: "+4.07 R",
  chartData: [
    { time: "04:00", pnl: 0 }, { time: "06:00", pnl: 1.2 }, 
    { time: "08:00", pnl: 2.5 }, { time: "10:00", pnl: 1.8 }, 
    { time: "12:00", pnl: 3.5 }, { time: "14:00", pnl: 4.07 }
  ]
};

export default function Home() {
  return (
    <main className="min-h-screen bg-black p-8">
      <div className="max-w-5xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex justify-between items-end border-b border-gray-800 pb-6">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-emerald-400 bg-clip-text text-transparent">
              Polymarket Quant
            </h1>
            <p className="text-gray-500 mt-2">BTC 15m Strategy • V3.1 Live</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
            <span className="text-green-500 text-sm font-medium">System Online</span>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <StatCard 
            title="Net Profit (24h)" 
            value={MOCK_DATA.netPnL} 
            type="positive" 
            subtext="Target: +5.0 R" 
          />
          <StatCard 
            title="Win Rate" 
            value={MOCK_DATA.winRate} 
            subtext="Based on 23 trades" 
          />
          <StatCard 
            title="Profit Factor" 
            value={MOCK_DATA.profitFactor} 
            type="positive"
            subtext="Excellent > 2.0" 
          />
        </div>

        {/* Chart Area */}
        <PnLChart data={MOCK_DATA.chartData} />

        {/* Recent Trades Table (Placeholder) */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
          <h3 className="text-gray-400 text-sm font-medium mb-4">Recent Activity</h3>
          <div className="text-gray-500 text-sm">
            Waiting for live data connection...
          </div>
        </div>

      </div>
    </main>
  );
}