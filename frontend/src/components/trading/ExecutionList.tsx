import { ArrowLeftRight } from "lucide-react";

export interface ExecutionItem {
  time: string;
  symbol: string;
  name: string;
  side: string;
  quantity: number;
  price: number;
  amount: number;
  fee?: number;
}

interface Props {
  data: ExecutionItem[];
  summary?: { buy_amount: number; sell_amount: number; total_fee?: number };
}

export function ExecutionList({ data, summary }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-xl border bg-card text-card-foreground shadow-sm p-6 text-center text-sm text-muted-foreground">
        今日暂无成交
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <ArrowLeftRight className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">今日成交</span>
        <span className="ml-auto text-[11px] text-muted-foreground">{data.length} 笔</span>
      </div>

      {summary && (
        <div className="grid grid-cols-3 gap-2 border-b bg-muted/20 px-4 py-2 text-xs">
          <div>
            <span className="text-muted-foreground">买入 </span>
            <span className="font-medium text-red-500 tabular-nums">
              {summary.buy_amount.toFixed(2)}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">卖出 </span>
            <span className="font-medium text-emerald-500 tabular-nums">
              {summary.sell_amount.toFixed(2)}
            </span>
          </div>
          {summary.total_fee != null && (
            <div>
              <span className="text-muted-foreground">费用 </span>
              <span className="font-medium tabular-nums">{summary.total_fee.toFixed(2)}</span>
            </div>
          )}
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b bg-muted/30">
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">时间</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">代码</th>
              <th className="px-3 py-2 text-left font-medium text-muted-foreground">名称</th>
              <th className="px-3 py-2 text-center font-medium text-muted-foreground">方向</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">数量</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">价格</th>
              <th className="px-3 py-2 text-right font-medium text-muted-foreground">金额</th>
            </tr>
          </thead>
          <tbody>
            {data.map((e, i) => (
              <tr key={`${e.symbol}_${e.time}_${i}`} className={i < data.length - 1 ? "border-b" : ""}>
                <td className="px-3 py-2 font-mono text-muted-foreground whitespace-nowrap">{e.time}</td>
                <td className="px-3 py-2 font-mono text-muted-foreground">{e.symbol}</td>
                <td className="px-3 py-2">{e.name}</td>
                <td className={`px-3 py-2 text-center font-medium ${e.side === "买入" ? "text-red-500" : "text-emerald-500"}`}>
                  {e.side}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">{e.quantity}</td>
                <td className="px-3 py-2 text-right tabular-nums">{e.price.toFixed(2)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{e.amount.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
