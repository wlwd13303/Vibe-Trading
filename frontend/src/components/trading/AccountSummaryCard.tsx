import { Wallet, TrendingUp, TrendingDown } from "lucide-react";

export interface AccountSummaryData {
  total_asset: number;
  cash_available: number;
  market_value: number;
  frozen_cash?: number;
  unrealized_pnl?: number;
}

export function AccountSummaryCard({ data }: { data: AccountSummaryData }) {
  const pnl = data.unrealized_pnl ?? 0;
  const isPositive = pnl >= 0;

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <Wallet className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">账户资产总览</span>
      </div>
      <div className="grid grid-cols-2 gap-4 p-4">
        <div>
          <div className="text-[11px] text-muted-foreground uppercase tracking-wide">总资产</div>
          <div className="mt-1 text-lg font-bold tabular-nums">
            {data.total_asset.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-muted-foreground uppercase tracking-wide">可用资金</div>
          <div className="mt-1 text-lg font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
            {data.cash_available.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-muted-foreground uppercase tracking-wide">持仓市值</div>
          <div className="mt-1 text-lg font-bold tabular-nums">
            {data.market_value.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}
          </div>
        </div>
        <div>
          <div className="text-[11px] text-muted-foreground uppercase tracking-wide">浮动盈亏</div>
          <div className={`mt-1 flex items-center gap-1 text-lg font-bold tabular-nums ${isPositive ? "text-red-500" : "text-emerald-500"}`}>
            {isPositive ? <TrendingUp className="h-4 w-4" /> : <TrendingDown className="h-4 w-4" />}
            {pnl.toLocaleString("zh-CN", { minimumFractionDigits: 2 })}
          </div>
        </div>
      </div>
    </div>
  );
}
