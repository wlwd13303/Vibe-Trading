import { useState, useRef, useEffect, type FormEvent } from "react";
import { Send, Loader2, Wallet, Briefcase, ArrowLeftRight, Sparkles, Bot } from "lucide-react";
import { api, type TradingChatResponse } from "@/lib/api";
import { AgentAvatar } from "@/components/chat/AgentAvatar";
import { AccountSummaryCard } from "@/components/trading/AccountSummaryCard";
import { PositionTable } from "@/components/trading/PositionTable";
import { OrderConfirmCard, type OrderPreviewData } from "@/components/trading/OrderConfirmCard";
import { OrderResultCard } from "@/components/trading/OrderResultCard";
import { OrderTypeSelectorCard } from "@/components/trading/OrderTypeSelectorCard";
import { PriceInputCard } from "@/components/trading/PriceInputCard";
import { ExecutionList } from "@/components/trading/ExecutionList";
import { PriceQuoteCard } from "@/components/trading/PriceQuoteCard";

/* ---------- Message types ---------- */

interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  cards: Record<string, unknown>[];
  error?: string;
  timestamp: number;
}

let _id = 0;
const nextId = () => `t_${++_id}`;

/** 从文本中提取 JSON 块作为卡片（前端兜底，仅当后端未返回卡片时使用）。 */
function extractCardsFromText(text: string): Record<string, unknown>[] {
  const cards: Record<string, unknown>[] = [];
  const regex = /```(?:json)?\s*\n?(\{.*?\}|\[.*?\])\s*```/gs;
  let match;
  while ((match = regex.exec(text)) !== null) {
    try {
      const parsed = JSON.parse(match[1]);
      if (parsed && typeof parsed === "object") {
        cards.push(parsed);
      }
    } catch {
      // skip invalid JSON
    }
  }
  return cards;
}

const DEFAULT_SUGGESTIONS = [
  "我有多少钱？",
  "我当前持有哪些股票？",
  "今天成交了哪些？",
  "查一下招商银行的代码和行情",
  "买入100股招商银行，限价42.50",
];

/* ---------- Card renderer ---------- */

interface CardRendererProps {
  card: Record<string, unknown>;
  onAction?: (text: string) => void;
}

function CardRenderer({ card, onAction }: CardRendererProps) {
  const kind = (card.kind as string) || "";
  try {
    switch (kind) {
      case "account_summary":
        return <AccountSummaryCard data={card as never} />;
      case "position_list":
        return <PositionTable data={(card.positions ?? []) as never} />;
      case "order_confirm": {
        const orderData = { ...card, status: "pending" as const };
        return <OrderConfirmCard data={orderData as OrderPreviewData} />;
      }
      case "order_result":
        return <OrderResultCard data={card as never} />;
      case "execution_list":
        return <ExecutionList data={(card.executions ?? []) as never} summary={card.summary as never} />;
      case "price_quote":
        return <PriceQuoteCard data={card as never} />;
      case "order_type_selector":
        return (
          <OrderTypeSelectorCard
            stock_name={card.stock_name as string}
            stock_code={card.stock_code as string}
            onSelect={(orderType) => onAction?.(`${orderType === "LIMIT" ? "限价单" : "市价单"}`)}
          />
        );
      case "price_input":
        return (
          <PriceInputCard
            stock_code={card.stock_code as string}
            stock_name={card.stock_name as string}
            pre_close={card.pre_close as number | null}
            limit_up={card.limit_up as number | null}
            limit_down={card.limit_down as number | null}
            onConfirm={(price) => onAction?.(`价格${price.toFixed(2)}`)}
          />
        );
      default:
        return null;
    }
  } catch {
    return null;
  }
}

/* ---------- Component ---------- */

export function TradingAgent() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
    });
  };

  useEffect(() => scrollToBottom(), [messages]);

  const sendMessage = async (content: string) => {
    if (!content.trim() || loading) return;

    const userTurn: ChatTurn = {
      id: nextId(), role: "user", text: content, cards: [], timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userTurn]);
    setInput("");
    setLoading(true);

    try {
      const res: TradingChatResponse = await api.tradingChat(content, sessionId);
      setSessionId(res.session_id);
      const cards = res.cards.length > 0 ? res.cards : extractCardsFromText(res.text);
      const assistantTurn: ChatTurn = {
        id: nextId(), role: "assistant", text: res.text, cards, timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantTurn]);
    } catch (err) {
      const errorTurn: ChatTurn = {
        id: nextId(), role: "assistant", text: "", cards: [],
        error: err instanceof Error ? err.message : "请求失败，请重试",
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorTurn]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (e: FormEvent) => { e.preventDefault(); sendMessage(input); };

  return (
    <div className="flex flex-col flex-1 min-w-0 overflow-hidden h-full">
      {/* Header */}
      <div className="border-b px-6 py-3 flex items-center gap-2 shrink-0">
        <Bot className="h-5 w-5 text-primary" />
        <div>
          <h1 className="text-sm font-semibold">交易助手</h1>
          <p className="text-[11px] text-muted-foreground">智能账号管理 · 实时行情 · 交易下单</p>
        </div>
      </div>

      {/* Messages */}
      <div ref={listRef} className="flex-1 overflow-auto p-6 scroll-smooth">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.length === 0 && !loading && (
            <div className="py-12 text-center">
              <Bot className="h-12 w-12 mx-auto text-primary/30 mb-4" />
              <h2 className="text-lg font-semibold text-foreground">你好！我是交易助手</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                我可以帮你查询账户资产、持仓、成交，以及执行交易指令
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {DEFAULT_SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    onClick={() => sendMessage(s)}
                    className="inline-flex items-center gap-1.5 rounded-full border bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  >
                    <Sparkles className="h-3 w-3" />
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((turn) => (
            <div key={turn.id}>
              {turn.role === "user" ? (
                <div className="flex justify-end gap-3">
                  <div className="max-w-[72%] rounded-2xl rounded-tr-sm bg-primary text-primary-foreground px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap">
                    {turn.text}
                  </div>
                  <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center shrink-0 mt-0.5">
                    <span className="text-xs font-medium text-muted-foreground">我</span>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex gap-3">
                    <AgentAvatar />
                    <div className="flex-1 min-w-0">
                      {turn.error ? (
                        <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                          {turn.error}
                        </div>
                      ) : turn.text ? (
                        <div className="prose prose-sm dark:prose-invert max-w-none leading-relaxed whitespace-pre-wrap">
                          {turn.text}
                        </div>
                      ) : null}
                    </div>
                  </div>
                  {/* Render cards */}
                  {turn.cards.length > 0 && (
                    <div className="pl-11 space-y-3">
                      {turn.cards.map((card, i) => (
                        <CardRenderer key={i} card={card} onAction={sendMessage} />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex gap-3">
              <AgentAvatar />
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin text-primary" />
                <span>交易助手思考中...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t p-4 bg-background/80 backdrop-blur-sm">
        <div className="max-w-3xl mx-auto flex gap-2 items-end">
          {/* Quick-action shortcuts */}
          <div className="flex gap-1 shrink-0 pb-1">
            <button
              type="button"
              onClick={() => sendMessage("我有多少钱？")}
              disabled={loading}
              className="p-2 rounded-lg border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
              title="查询账户资产"
            >
              <Wallet className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => sendMessage("我当前持有哪些股票？")}
              disabled={loading}
              className="p-2 rounded-lg border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
              title="查询持仓"
            >
              <Briefcase className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => sendMessage("今天成交了哪些？")}
              disabled={loading}
              className="p-2 rounded-lg border text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-40"
              title="今日成交"
            >
              <ArrowLeftRight className="h-4 w-4" />
            </button>
          </div>
          <textarea
            ref={inputRef}
            value={input}
            rows={1}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage(input);
              }
            }}
            placeholder="输入查询或交易指令..."
            className="flex-1 px-4 py-2.5 rounded-xl border bg-background text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 transition-shadow resize-none max-h-32 overflow-y-auto"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading}
            className="px-4 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-medium disabled:opacity-40 hover:opacity-90 transition-opacity"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
      </form>
    </div>
  );
}
