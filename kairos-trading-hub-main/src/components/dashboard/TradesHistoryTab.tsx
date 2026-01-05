import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, Clock, DollarSign, Activity } from "lucide-react";
import { getApiUrl } from "@/lib/api";

interface Trade {
  id: number;
  symbol: string;
  side: string;
  size: number;
  price: number | null;
  order_id: string | null;
  status: string;
  pnl: number | null;
  fees: number | null;
  execution_time: string;
  notes: string | null;
}

export function TradesHistoryTab() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState({
    totalTrades: 0,
    winRate: 0,
    totalPnL: 0,
    avgWin: 0,
    avgLoss: 0
  });

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const fetchTrades = async () => {
    try {
      const response = await fetch(getApiUrl("/api/trade-history?limit=100"));
      const data = await response.json();

      if (data.status === "success" && data.trades) {
        setTrades(data.trades);
        calculateStats(data.trades);
      }
      setIsLoading(false);
    } catch (error) {
      console.error("Failed to fetch trades:", error);
      setIsLoading(false);
    }
  };

  const calculateStats = (tradesList: Trade[]) => {
    const tradesWithPnL = tradesList.filter(t => t.pnl !== null);
    const wins = tradesWithPnL.filter(t => (t.pnl || 0) > 0);
    const losses = tradesWithPnL.filter(t => (t.pnl || 0) < 0);

    const totalPnL = tradesWithPnL.reduce((sum, t) => sum + (t.pnl || 0), 0);
    const winRate = tradesWithPnL.length > 0 ? (wins.length / tradesWithPnL.length) * 100 : 0;
    const avgWin = wins.length > 0 ? wins.reduce((sum, t) => sum + (t.pnl || 0), 0) / wins.length : 0;
    const avgLoss = losses.length > 0 ? losses.reduce((sum, t) => sum + (t.pnl || 0), 0) / losses.length : 0;

    setStats({
      totalTrades: tradesList.length,
      winRate: Math.round(winRate * 10) / 10,
      totalPnL: Math.round(totalPnL * 100) / 100,
      avgWin: Math.round(avgWin * 100) / 100,
      avgLoss: Math.round(avgLoss * 100) / 100
    });
  };

  const formatPrice = (price: number | null) => {
    if (!price) return "N/A";
    if (price >= 1000) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (price >= 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(4)}`;
  };

  const formatTime = (timeStr: string) => {
    const date = new Date(timeStr);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getSymbolDisplay = (symbol: string) => {
    return symbol.replace("cmt_", "").replace("usdt", "").toUpperCase();
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-2 mb-1">
          <Activity className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Trade History</span>
        </div>
        <p className="text-xs text-muted-foreground">All executed trades and performance</p>
      </div>

      {/* Stats Summary */}
      <div className="p-4 border-b border-border bg-card/50">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-background/50 rounded-lg p-3">
            <div className="text-[10px] text-muted-foreground uppercase mb-1">Total Trades</div>
            <div className="text-lg font-mono font-bold text-foreground">{stats.totalTrades}</div>
          </div>
          <div className="bg-background/50 rounded-lg p-3">
            <div className="text-[10px] text-muted-foreground uppercase mb-1">Win Rate</div>
            <div className={cn(
              "text-lg font-mono font-bold",
              stats.winRate >= 50 ? "text-success" : "text-destructive"
            )}>
              {stats.winRate.toFixed(1)}%
            </div>
          </div>
          <div className="bg-background/50 rounded-lg p-3">
            <div className="text-[10px] text-muted-foreground uppercase mb-1">Total P&L</div>
            <div className={cn(
              "text-lg font-mono font-bold",
              stats.totalPnL >= 0 ? "text-success" : "text-destructive"
            )}>
              {stats.totalPnL >= 0 ? '+' : ''}{formatPrice(stats.totalPnL)}
            </div>
          </div>
          <div className="bg-background/50 rounded-lg p-3">
            <div className="text-[10px] text-muted-foreground uppercase mb-1">Avg Win/Loss</div>
            <div className="text-sm font-mono text-foreground">
              <span className="text-success">+{formatPrice(stats.avgWin)}</span> / <span className="text-destructive">{formatPrice(stats.avgLoss)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Trades List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4 animate-pulse">
              <Activity className="w-8 h-8 text-muted-foreground/50" />
            </div>
            <div className="text-sm font-medium text-muted-foreground mb-1">
              Loading Trades...
            </div>
          </div>
        ) : trades.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Activity className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
            <div className="text-sm font-medium text-muted-foreground mb-1">
              No Trades Yet
            </div>
            <div className="text-xs text-muted-foreground/60">
              Your trade history will appear here
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            {trades.map((trade) => (
              <div
                key={trade.id}
                className={cn(
                  "rounded-lg p-3 border transition-all hover:bg-card/50",
                  trade.side === "buy" ? "border-success/20 bg-success/5" : "border-destructive/20 bg-destructive/5"
                )}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {trade.side === "buy" ? (
                      <TrendingUp className="w-4 h-4 text-success" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-destructive" />
                    )}
                    <span className="text-sm font-medium text-foreground">
                      {getSymbolDisplay(trade.symbol)}
                    </span>
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded-full font-medium",
                      trade.side === "buy"
                        ? "bg-success/20 text-success"
                        : "bg-destructive/20 text-destructive"
                    )}>
                      {trade.side.toUpperCase()}
                    </span>
                  </div>
                  {trade.pnl !== null && (
                    <div className={cn(
                      "text-sm font-mono font-bold",
                      trade.pnl >= 0 ? "text-success" : "text-destructive"
                    )}>
                      {trade.pnl >= 0 ? '+' : ''}{formatPrice(trade.pnl)}
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground mb-2">
                  <div className="flex items-center gap-1">
                    <DollarSign className="w-3 h-3" />
                    <span>Size: {trade.size}</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <DollarSign className="w-3 h-3" />
                    <span>Price: {formatPrice(trade.price)}</span>
                  </div>
                </div>

                {trade.notes && (
                  <div className="text-xs text-muted-foreground/60 mb-2 line-clamp-2">
                    {trade.notes}
                  </div>
                )}

                <div className="flex items-center justify-between text-[10px] text-muted-foreground/60">
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    <span>{formatTime(trade.execution_time)}</span>
                  </div>
                  {trade.order_id && (
                    <span className="font-mono">#{trade.order_id.slice(-8)}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

