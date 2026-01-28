"use client";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function PnLChart({ data }: any) {
  return (
    <div className="h-[300px] w-full bg-gray-900 border border-gray-800 rounded-xl p-4">
      <h3 className="text-gray-400 text-sm font-medium mb-4">Equity Curve (Intraday)</h3>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis dataKey="time" stroke="#555" fontSize={12} tickLine={false} />
          <YAxis stroke="#555" fontSize={12} tickLine={false} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#111', border: '1px solid #333' }}
            itemStyle={{ color: '#fff' }}
          />
          <Line 
            type="monotone" 
            dataKey="pnl" 
            stroke="#10b981" 
            strokeWidth={2} 
            dot={false}
            activeDot={{ r: 6, fill: '#10b981' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}