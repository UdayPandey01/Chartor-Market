import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, BarChart3, AlertTriangle, Target } from "lucide-react";

interface RiskMetrics {
  totalTrades: number;
  winRate: number;
  totalPnL: number;
  sharpeRatio: number;
  maxDrawdown: number;
  profitFactor: number;
  avgTrade: number;
  bestTrade: number;
  worstTrade: number;
}

export function RiskMetricsTab() {
  const [metrics, setMetrics] = useState<RiskMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchMetrics = async () => {
    try {
      const response = await fetch("/api/risk-metrics");
      const data = await response.json();
      
      if (data.status === "success" && data.metrics) {
        setMetrics(data.metrics);
      }
      setIsLoading(false);
    } catch (error) {
      console.error("Failed to fetch risk metrics:", error);
      setIsLoading(false);
    }
  };

  const formatPrice = (price: number) => {
    if (price >= 1000) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (price >= 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(4)}`;
  };

  const getSharpeColor = (sharpe: number) => {
    if (sharpe >= 2) return "text-success";
    if (sharpe >= 1) return "text-warning";
    return "text-destructive";
  };

  const getDrawdownColor = (dd: number) => {
    if (dd <= -20) return "text-destructive";
    if (dd <= -10) return "text-warning";
    return "text-muted-foreground";
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center py-8">
        <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4 animate-pulse">
          <BarChart3 className="w-8 h-8 text-muted-foreground/50" />
        </div>
        <div className="text-sm font-medium text-muted-foreground mb-1">
          Calculating Metrics...
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center py-8">
        <BarChart3 className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
        <div className="text-sm font-medium text-muted-foreground mb-1">
          No Data Available
        </div>
        <div className="text-xs text-muted-foreground/60">
          Need more trades to calculate metrics
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-2 mb-1">
          <BarChart3 className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Risk Metrics</span>
        </div>
        <p className="text-xs text-muted-foreground">Performance analytics and risk indicators</p>
      </div>

      {/* Key Metrics Grid */}
      <div className="p-4 border-b border-border bg-card/50">
        <div className="grid grid-cols-2 gap-3">
          {/* Sharpe Ratio */}
          <div className="bg-background/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <Target className="w-3 h-3 text-muted-foreground" />
              <div className="text-[10px] text-muted-foreground uppercase">Sharpe Ratio</div>
            </div>
            <div className={cn("text-xl font-mono font-bold", getSharpeColor(metrics.sharpeRatio))}>
              {metrics.sharpeRatio.toFixed(2)}
            </div>
            <div className="text-[10px] text-muted-foreground/60 mt-1">
              {metrics.sharpeRatio >= 2 ? "Excellent" : metrics.sharpeRatio >= 1 ? "Good" : "Poor"}
            </div>
          </div>

          {/* Max Drawdown */}
          <div className="bg-background/50 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle className="w-3 h-3 text-muted-foreground" />
              <div className="text-[10px] text-muted-foreground uppercase">Max Drawdown</div>
            </div>
            <div className={cn("text-xl font-mono font-bold", getDrawdownColor(metrics.maxDrawdown))}>
              {metrics.maxDrawdown.toFixed(2)}%
            </div>
            <div className="text-[10px] text-muted-foreground/60 mt-1">
              {Math.abs(metrics.maxDrawdown) <= 10 ? "Low Risk" : Math.abs(metrics.maxDrawdown) <= 20 ? "Moderate" : "High Risk"}
            </div>
          </div>

          {/* Profit Factor */}
          <div className="bg-background/50 rounded-lg p-3">
            <div className="text-[10px] text-muted-foreground uppercase mb-1">Profit Factor</div>
            <div className={cn(
              "text-xl font-mono font-bold",
              metrics.profitFactor >= 1.5 ? "text-success" : metrics.profitFactor >= 1 ? "text-warning" : "text-destructive"
            )}>
              {metrics.profitFactor.toFixed(2)}
            </div>
            <div className="text-[10px] text-muted-foreground/60 mt-1">
              {metrics.profitFactor >= 1.5 ? "Strong" : metrics.profitFactor >= 1 ? "Positive" : "Negative"}
            </div>
          </div>

          {/* Win Rate */}
          <div className="bg-background/50 rounded-lg p-3">
            <div className="text-[10px] text-muted-foreground uppercase mb-1">Win Rate</div>
            <div className={cn(
              "text-xl font-mono font-bold",
              metrics.winRate >= 50 ? "text-success" : "text-destructive"
            )}>
              {metrics.winRate.toFixed(1)}%
            </div>
            <div className="text-[10px] text-muted-foreground/60 mt-1">
              {metrics.totalTrades} trades
            </div>
          </div>
        </div>
      </div>

      {/* Detailed Stats */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-3">
        {/* Total P&L */}
        <div className="bg-background/50 rounded-lg p-4">
          <div className="text-xs text-muted-foreground uppercase mb-2">Total Performance</div>
          <div className={cn(
            "text-2xl font-mono font-bold mb-1",
            metrics.totalPnL >= 0 ? "text-success" : "text-destructive"
          )}>
            {metrics.totalPnL >= 0 ? '+' : ''}{formatPrice(metrics.totalPnL)}
          </div>
          <div className="text-xs text-muted-foreground">
            Average per trade: {formatPrice(metrics.avgTrade)}
          </div>
        </div>

        {/* Best & Worst Trades */}
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-success/5 border border-success/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <TrendingUp className="w-4 h-4 text-success" />
              <div className="text-xs text-muted-foreground uppercase">Best Trade</div>
            </div>
            <div className="text-lg font-mono font-bold text-success">
              +{formatPrice(metrics.bestTrade)}
            </div>
          </div>

          <div className="bg-destructive/5 border border-destructive/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <TrendingDown className="w-4 h-4 text-destructive" />
              <div className="text-xs text-muted-foreground uppercase">Worst Trade</div>
            </div>
            <div className="text-lg font-mono font-bold text-destructive">
              {formatPrice(metrics.worstTrade)}
            </div>
          </div>
        </div>

        {/* Risk Assessment */}
        <div className="bg-background/50 rounded-lg p-4">
          <div className="text-xs text-muted-foreground uppercase mb-3">Risk Assessment</div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Sharpe Ratio</span>
              <span className={cn("text-xs font-mono font-medium", getSharpeColor(metrics.sharpeRatio))}>
                {metrics.sharpeRatio.toFixed(2)} {metrics.sharpeRatio >= 2 ? "OK" : metrics.sharpeRatio >= 1 ? "WARN" : "FAIL"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Max Drawdown</span>
              <span className={cn("text-xs font-mono font-medium", getDrawdownColor(metrics.maxDrawdown))}>
                {metrics.maxDrawdown.toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Profit Factor</span>
              <span className={cn(
                "text-xs font-mono font-medium",
                metrics.profitFactor >= 1.5 ? "text-success" : metrics.profitFactor >= 1 ? "text-warning" : "text-destructive"
              )}>
                {metrics.profitFactor.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

