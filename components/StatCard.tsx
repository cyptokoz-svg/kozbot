import { ArrowUpRight, ArrowDownRight, Activity, DollarSign } from "lucide-react";

export default function StatCard({ title, value, subtext, type = "neutral" }: any) {
  let colorClass = "text-gray-200";
  if (type === "positive") colorClass = "text-green-400";
  if (type === "negative") colorClass = "text-red-400";

  return (
    <div className="bg-gray-900 border border-gray-800 p-6 rounded-xl">
      <div className="flex justify-between items-start">
        <div>
          <p className="text-gray-400 text-sm font-medium">{title}</p>
          <h3 className={`text-3xl font-bold mt-2 ${colorClass}`}>{value}</h3>
        </div>
        <div className={`p-2 rounded-lg bg-gray-800 ${colorClass}`}>
          {type === "positive" ? <ArrowUpRight /> : <Activity />}
        </div>
      </div>
      <p className="text-gray-500 text-sm mt-4">{subtext}</p>
    </div>
  );
}