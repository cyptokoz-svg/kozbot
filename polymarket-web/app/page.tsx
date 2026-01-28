"use client";
import { useEffect, useState } from 'react';
import StatCard from "../components/StatCard";
import PnLChart from "../components/PnLChart";

export default function Home() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  // Fetch Data from local JSON (served by Vercel from public folder)
  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/data.json?t=' + new Date().getTime()); // Anti-cache
        const json = await res.json();
        setData(json);
      } catch (e) {
        console.error("Failed to load data", e);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 60000); // Poll every minute
    return () => clearInterval(interval);
  }, []);

  if (loading) return <div className="min-h-screen bg-black text-white p-10">Loading Quant Data...</div>;
  if (!data) return <div className="min-h-screen bg-black text-white p-10">Data not found. Run sync script first.</div>;

  return (
    <main className="min-h-screen bg-black p-4 md:p-8 font-sans text-gray-100">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-end border-b border-gray-800 pb-6 gap-4">
          <div>
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-500 via-indigo-500 to-purple-500 bg-clip-text text-transparent">
              Polymarket Quant
            </h1>
            <p className="text-gray-500 mt-2 flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-gray-800 text-xs border border-gray-700">V3.1</span>
              <span>BTC 15m Strategy</span>
            </p>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2 justify-end">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
              <span className="text-green-500 text-xs font-mono font-bold tracking-wider">SYSTEM ONLINE</span>
            </div>
            <p className="text-gray-600 text-xs mt-1 font-mono">Last Update: {data.updatedAt}</p>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <StatCard 
            title="Net Profit (Total)" 
            value={data.stats.netPnL} 
            type={data.stats.netPnL.includes("+") ? "positive" : "negative"}
            subtext={`${data.stats.totalTrades} Trades Executed`} 
          />
          <StatCard 
            title="Win Rate" 
            value={data.stats.winRate} 
            subtext="Performance Metric" 
          />
          <StatCard 
            title="Profit Factor" 
            value={data.stats.profitFactor} 
            type={parseFloat(data.stats.profitFactor) > 1.5 ? "positive" : "neutral"}
            subtext="Target > 1.5" 
          />
        </div>

        {/* Main Content Split */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Left: Chart (2 cols) */}
          <div className="lg:col-span-2 space-y-6">
            <PnLChart data={data.chartData} />
          </div>

          {/* Right: Recent Trades Table (1 col) */}
          <div className="bg-gray-900/50 border border-gray-800 rounded-xl overflow-hidden backdrop-blur-sm">
            <div className="p-4 border-b border-gray-800 bg-gray-900">
              <h3 className="text-gray-300 text-sm font-semibold">Live Feed</h3>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-900/50 text-gray-500 sticky top-0">
                  <tr>
                    <th className="p-3 font-medium">Time</th>
                    <th className="p-3 font-medium">Type</th>
                    <th className="p-3 font-medium text-right">PnL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {data.recentTrades.map((t: any, i: number) => {
                    const isWin = parseFloat(t.pnl) > 0;
                    const isLoss = parseFloat(t.pnl) < 0;
                    return (
                      <tr key={i} className="hover:bg-gray-800/50 transition-colors">
                        <td className="p-3 text-gray-400 font-mono">{t.shortTime || "-"}</td>
                        <td className="p-3">
                          <span className={`px-1.5 py-0.5 rounded ${
                            t.direction === "UP" ? "bg-green-900/30 text-green-400" : "bg-red-900/30 text-red-400"
                          }`}>
                            {t.direction || t.type}
                          </span>
                        </td>
                        <td className={`p-3 text-right font-medium font-mono ${
                          isWin ? "text-green-400" : isLoss ? "text-red-400" : "text-gray-400"
                        }`}>
                          {t.pnl ? (parseFloat(t.pnl) * 100).toFixed(1) + "%" : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}