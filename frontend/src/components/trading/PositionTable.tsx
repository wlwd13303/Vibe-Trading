import { Briefcase } from "lucide-react";

export interface PositionItem {
  symbol: string;
  name: string;
  quantity: number;
  available_qty?: number;
  cost_price: number;
  market_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_ratio?: number;
}

export function PositionTable({ data }: { data: PositionItem[] }) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-xl border bg-card text-card-foreground shadow-sm p-6 text-center text-sm text-muted-foreground">
        暂无持仓
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <Briefcase className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">当前持仓</span>
        <span className="ml-auto text-[11px] text-muted-foreground">{data.length} 只标的</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/30">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">代码</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">名称</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">持股</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">成本价</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">现价</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">市值</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">盈亏</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">盈亏比</th>
            </tr>
          </thead>
          <tbody>
            {data.map((p, i) => {
              const pnlPositive = p.unrealized_pnl >= 0;
              return (
                <tr key={p.symbol} className={i < data.length - 1 ? "border-b" : ""}>
                  <td className="px-3 py-2.5 font-mono text-muted-foreground">{p.symbol}</td>
                  <td className="px-3 py-2.5 font-medium">{p.name}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{p.quantity}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{p.cost_price.toFixed(2)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{p.market_price.toFixed(2)}</td>
                  <td className="px-3 py-2.5 text-right tabular-nums">{p.market_value.toFixed(2)}</td>
                  <td className={`px-3 py-2.5 text-right tabular-nums font-medium ${pnlPositive ? "text-red-500" : "text-emerald-500"}`}>
                    {p.unrealized_pnl.toFixed(2)}
                  </td>
                  <td className={`px-3 py-2.5 text-right tabular-nums font-medium ${pnlPositive ? "text-red-500" : "text-emerald-500"}`}>
                    {p.unrealized_pnl_ratio != null ? `${p.unrealized_pnl_ratio >= 0 ? "+" : ""}${p.unrealized_pnl_ratio.toFixed(2)}%` : "--"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
