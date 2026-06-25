import { TrendingUp, TrendingDown, Minus } from "lucide-react";

export interface PriceQuoteData {
  stock_code: string;
  price: number;
  update_time?: string;
  pre_close?: number | null;
  limit_up?: number | null;
  limit_down?: number | null;
  source?: string;
}

export function PriceQuoteCard({ data }: { data: PriceQuoteData }) {
  const change = data.pre_close ? data.price - data.pre_close : 0;
  const pctChg = data.pre_close && data.pre_close > 0 ? (change / data.pre_close) * 100 : 0;
  const isUp = change > 0;
  const isDown = change < 0;

  const changeColor = isUp
    ? "text-red-500"
    : isDown
      ? "text-emerald-500"
      : "text-muted-foreground";

  const TrendIcon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <TrendIcon className={`h-4 w-4 ${changeColor}`} />
          <span className="text-sm font-semibold">实时行情</span>
        </div>
        {data.source && (
          <span className="text-[10px] text-muted-foreground">
            来源: {data.source === "assetsplit_sdk" ? "实时" : "日线"}
          </span>
        )}
      </div>
      <div className="p-4">
        <div className="flex items-baseline justify-between">
          <div>
            <div className="text-lg font-bold">{data.stock_code}</div>
            <div className="text-xs text-muted-foreground">{data.update_time ?? "--"}</div>
          </div>
          <div className="text-right">
            <div className={`text-3xl font-bold tabular-nums ${changeColor}`}>
              {data.price.toFixed(2)}
            </div>
            <div className={`flex items-center justify-end gap-1 text-sm tabular-nums ${changeColor}`}>
              <span>{change >= 0 ? "+" : ""}{change.toFixed(2)}</span>
              <span>({pctChg >= 0 ? "+" : ""}{pctChg.toFixed(2)}%)</span>
            </div>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 border-t pt-3 text-xs">
          {data.pre_close != null && (
            <div className="text-center">
              <div className="text-muted-foreground">昨收</div>
              <div className="mt-0.5 font-medium tabular-nums">{data.pre_close.toFixed(2)}</div>
            </div>
          )}
          {data.limit_up != null && (
            <div className="text-center">
              <div className="text-muted-foreground">涨停</div>
              <div className="mt-0.5 font-medium tabular-nums text-red-500">{data.limit_up.toFixed(2)}</div>
            </div>
          )}
          {data.limit_down != null && (
            <div className="text-center">
              <div className="text-muted-foreground">跌停</div>
              <div className="mt-0.5 font-medium tabular-nums text-emerald-500">{data.limit_down.toFixed(2)}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
