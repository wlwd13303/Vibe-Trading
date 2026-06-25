import { useState } from "react";
import { ShoppingCart, Check, X, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

export interface OrderPreviewData {
  card_id?: string;
  stock_code: string;
  stock_name: string;
  side: "BUY" | "SELL";
  quantity: number;
  price: number;
  price_type: "LIMIT" | "MARKET";
  estimated_amount?: number;
  risk_tips?: string;
  status?: "pending" | "confirmed" | "cancelled" | "error" | "committing";
  error?: string;
}

interface Props {
  data: OrderPreviewData;
}

export function OrderConfirmCard({ data }: Props) {
  const [committing, setCommitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);

  const sideText = data.side === "BUY" ? "买入" : "卖出";
  const sideColor = data.side === "BUY"
    ? "border-red-500/30 bg-red-500/5 text-red-600 dark:text-red-400"
    : "border-emerald-500/30 bg-emerald-500/5 text-emerald-600 dark:text-emerald-400";

  // ── 已完成状态 ──
  if (result || data.status === "confirmed" || data.status === "committing") {
    const ok = result?.ok ?? true;
    return (
      <div className={`rounded-xl border shadow-sm p-4 ${
        ok ? "border-emerald-500/30 bg-emerald-500/5" : "border-destructive/30 bg-destructive/5"
      }`}>
        <div className="flex items-center gap-2">
          {committing || data.status === "committing" ? (
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          ) : ok ? (
            <Check className="h-4 w-4 text-emerald-500" />
          ) : (
            <X className="h-4 w-4 text-destructive" />
          )}
          <span className="text-sm font-semibold">
            {committing || data.status === "committing" ? "提交中..." : ok ? "下单成功" : "下单失败"}
          </span>
        </div>
        {result?.msg && <p className="mt-1 text-xs text-muted-foreground">{result.msg}</p>}
        {data.error && <p className="mt-1 text-xs text-destructive">{data.error}</p>}
      </div>
    );
  }

  if (data.status === "cancelled") {
    return (
      <div className="rounded-xl border bg-card text-card-foreground shadow-sm p-4">
        <div className="flex items-center gap-2 text-muted-foreground">
          <X className="h-4 w-4" />
          <span className="text-sm font-semibold">已取消</span>
        </div>
      </div>
    );
  }

  const estimatedAmount = data.estimated_amount ?? data.price * data.quantity;

  // ── 提交下单 ──
  const handleCommit = async () => {
    if (!data.card_id) return;
    setCommitting(true);
    data.status = "committing";
    try {
      const res = await api.tradingOrderCommit(data.card_id);
      setResult({ ok: true, msg: res.message || "委托已提交" });
      data.status = "confirmed";
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "下单失败";
      setResult({ ok: false, msg });
      data.status = "error";
      data.error = msg;
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="rounded-xl border bg-card text-card-foreground shadow-sm">
      <div className="flex items-center gap-2 border-b px-4 py-3">
        <ShoppingCart className="h-4 w-4 text-primary" />
        <span className="text-sm font-semibold">确认下单</span>
      </div>
      <div className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium">{data.stock_name}</span>
          <span className="font-mono text-xs text-muted-foreground">{data.stock_code}</span>
        </div>

        <div className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${sideColor}`}>
          {sideText}
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs">
          <div>
            <div className="text-muted-foreground">数量</div>
            <div className="mt-0.5 font-medium tabular-nums">{data.quantity} 股</div>
          </div>
          <div>
            <div className="text-muted-foreground">价格</div>
            <div className="mt-0.5 font-medium tabular-nums">
              {data.price_type === "MARKET" ? "市价" : `限价 ${data.price.toFixed(2)}`}
            </div>
          </div>
          <div className="col-span-2">
            <div className="text-muted-foreground">预计金额</div>
            <div className="mt-0.5 font-medium tabular-nums">
              {estimatedAmount.toLocaleString("zh-CN", { minimumFractionDigits: 2 })} 元
            </div>
          </div>
        </div>

        {data.risk_tips && (
          <div className="rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2 text-[11px] text-amber-700 dark:text-amber-400">
            ⚠ {data.risk_tips}
          </div>
        )}

        <button
          onClick={handleCommit}
          disabled={committing || !data.card_id}
          className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-40"
        >
          {committing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
          确认下单
        </button>
      </div>
    </div>
  );
}
