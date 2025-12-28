import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import { Asset } from "@/types/trading";
import { cn } from "@/lib/utils";
import {
  Shield,
  Zap,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Power,
  Lock,
  Unlock,
  XCircle,
  Brain,
  Clock
} from "lucide-react";

interface SentinelControlTabProps {
  asset: Asset;
  onAuthorizeTrade: (type: 'long' | 'short') => void;
  onForceClose: () => void;
}

interface AIAnalysis {
  symbol: string;
  decision: string;
  confidence: number;
  reasoning: string;
  price: number;
  rsi: number;
  trend: string;
  timestamp: string;
}

interface AIStatus {
  available: boolean;
  using_fallback: boolean;
  quota_exceeded: boolean;
  calls_remaining: number;
  cooldown_until: string | null;
}

// Helper function to get consistent WEEX symbol format
const getWeexSymbol = (asset: Asset): string => {
  if (asset.raw_symbol) {
    return asset.raw_symbol;
  }
  // Convert "BTC/USDT" or "BTC" to "cmt_btcusdt"
  const symbolPart = asset.symbol.split("/")[0].toLowerCase();
  return `cmt_${symbolPart}usdt`;
};

export function SentinelControlTab({ asset, onAuthorizeTrade, onForceClose }: SentinelControlTabProps) {
  const [autoTrading, setAutoTrading] = useState(false);
  const [riskTolerance, setRiskTolerance] = useState(20);
  const [aiAnalysis, setAiAnalysis] = useState<AIAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [aiStatus, setAiStatus] = useState<AIStatus | null>(null);

  // Fetch trade settings and AI status on mount
  useEffect(() => {
    fetchTradeSettings();
    fetchAIStatus();
    // Auto-trigger analysis when component mounts (Sentinel tab opened)
    // Add small delay to avoid immediate trigger on every render
    const timer = setTimeout(() => {
      triggerAnalysis();
    }, 500);
    return () => clearTimeout(timer);
  }, []);

  const fetchAIStatus = async () => {
    try {
      const response = await fetch("/api/ai-status");
      if (response.ok) {
        const status = await response.json();
        setAiStatus(status);
      }
    } catch (error) {
      console.error("Failed to fetch AI status:", error);
    }
  };

  // Trigger analysis when asset changes or when auto-trading is enabled
  useEffect(() => {
    if (autoTrading) {
      // Don't trigger immediately - let the background sentinel handle it
      // Just fetch the latest analysis
      fetchAIAnalysis();
      // Poll for new analysis every 30 seconds when auto-trading is on
      const interval = setInterval(fetchAIAnalysis, 30000);
      return () => clearInterval(interval);
    } else {
      // When not auto-trading, just fetch latest analysis if available
      fetchAIAnalysis();
    }
  }, [asset, autoTrading]);

  const fetchTradeSettings = async () => {
    try {
      const response = await fetch("/api/trade-settings");
      const data = await response.json();
      setAutoTrading(data.auto_trading || false);
      setRiskTolerance(data.risk_tolerance || 20);
    } catch (error) {
      console.error("Failed to fetch trade settings:", error);
    }
  };

  const triggerAnalysis = async () => {
    try {
      // Get consistent WEEX symbol format
      const symbol = getWeexSymbol(asset);
      
      setIsLoading(true);

      // Try with request body first
      let response = await fetch("/api/trigger-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol })
      });

      // If 422 error, try with query parameter
      if (!response.ok && response.status === 422) {
        response = await fetch(`/api/trigger-analysis?symbol=${encodeURIComponent(symbol)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" }
        });
      }

      if (!response.ok) {
        const errorText = await response.text();
        console.error("Failed to trigger analysis:", response.status, errorText);
        setIsLoading(false);
        return;
      }

      const data = await response.json();

      if (data.status === "success") {
        setAiAnalysis({
          symbol: data.symbol,
          decision: data.decision,
          confidence: data.confidence,
          reasoning: data.reasoning,
          price: data.price,
          rsi: data.rsi,
          trend: data.trend,
          timestamp: new Date().toISOString()
        });
      } else {
        console.error("Analysis failed:", data.msg);
      }
      setIsLoading(false);
    } catch (error) {
      console.error("Failed to trigger analysis:", error);
      setIsLoading(false);
    }
  };

  const fetchAIAnalysis = async () => {
    try {
      // Get consistent WEEX symbol format
      const symbol = getWeexSymbol(asset);
      const response = await fetch(`/api/ai-analysis?symbol=${symbol}`);

      if (!response.ok) {
        setIsLoading(false);
        return;
      }

      const data = await response.json();

      if (data && data.decision) {
        setAiAnalysis(data);
      }
      setIsLoading(false);
    } catch (error) {
      console.error("Failed to fetch AI analysis:", error);
      setIsLoading(false);
    }
  };

  const handleAutoTradingToggle = async (checked: boolean) => {
    setAutoTrading(checked);

    try {
      // Update current symbol when toggling
      const symbol = getWeexSymbol(asset);

      await fetch("/api/trade-settings", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          auto_trading: String(checked),
          current_symbol: symbol
        })
      });
    } catch (error) {
      console.error("Failed to update auto-trading:", error);
    }
  };

  const handleRiskToleranceChange = async (value: number[]) => {
    const newValue = value[0];
    setRiskTolerance(newValue);

    try {
      await fetch("/api/trade-settings", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          risk_tolerance: String(newValue)
        })
      });
    } catch (error) {
      console.error("Failed to update risk tolerance:", error);
    }
  };

  const handleAuthorizeTrade = async (decision: string) => {
    try {
      const symbol = getWeexSymbol(asset);
      const action = decision === "BUY" ? "long" : "short";

      const response = await fetch("/api/trade", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          action: action,
          symbol: symbol
        })
      });

      const result = await response.json();

      if (result.status === "success") {
        console.log("Trade executed:", result);
        onAuthorizeTrade(action);
      } else {
        console.error("Trade failed:", result.msg);
      }
    } catch (error) {
      console.error("Failed to execute trade:", error);
    }
  };

  const formatPrice = (price: number) => {
    if (price >= 1000) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (price >= 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(4)}`;
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-2 mb-1">
          <Shield className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-foreground">Chartor Sentinel</span>
        </div>
        <p className="text-xs text-muted-foreground">AI-powered trade signals & execution</p>
        {aiStatus && aiStatus.using_fallback && (
          <div className="mt-2 px-2 py-1 bg-warning/10 border border-warning/20 rounded text-xs text-warning">
            Using fallback engine (Gemini quota exceeded)
          </div>
        )}
      </div>

      {/* Auto-Trading Toggle */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-8 h-8 rounded-lg flex items-center justify-center transition-colors",
              autoTrading ? "bg-success/20" : "bg-muted"
            )}>
              {autoTrading ? (
                <Unlock className="w-4 h-4 text-success" />
              ) : (
                <Lock className="w-4 h-4 text-muted-foreground" />
              )}
            </div>
            <div>
              <div className="text-sm font-medium text-foreground">Auto-Trading Mode</div>
              <div className="text-xs text-muted-foreground">
                {autoTrading ? "Autonomous execution active" : "Manual approval required"}
              </div>
            </div>
          </div>
          <Switch
            checked={autoTrading}
            onCheckedChange={handleAutoTradingToggle}
            className="data-[state=checked]:bg-success"
          />
        </div>

        {/* Risk Tolerance Slider */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">Risk Tolerance</span>
            <span className="text-xs font-mono text-foreground">{riskTolerance}%</span>
          </div>
          <Slider
            value={[riskTolerance]}
            onValueChange={handleRiskToleranceChange}
            min={20}
            max={30}
            step={1}
            className="w-full"
          />
          <div className="flex justify-between text-[10px] text-muted-foreground/60">
            <span>Conservative (20%)</span>
            <span>Aggressive (30%)</span>
          </div>
        </div>
      </div>

      {/* AI Analysis Display */}
      <div className="flex-1 p-4 overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4 animate-pulse">
              <Brain className="w-8 h-8 text-muted-foreground/50" />
            </div>
            <div className="text-sm font-medium text-muted-foreground mb-1">
              Analyzing Market...
            </div>
            <div className="text-xs text-muted-foreground/60">
              AI is processing {asset.symbol} data...
            </div>
          </div>
        ) : aiAnalysis && aiAnalysis.decision !== "WAIT" ? (
          <div className={cn(
            "rounded-xl p-4 border-2 transition-all duration-500 animate-fade-in",
            aiAnalysis.decision === 'BUY'
              ? "bg-success/5 border-success/30 shadow-[0_0_30px_hsl(var(--success)/0.15)]"
              : "bg-destructive/5 border-destructive/30 shadow-[0_0_30px_hsl(var(--destructive)/0.15)]"
          )}>
            {/* Analysis Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <div className={cn(
                  "relative w-3 h-3 rounded-full",
                  aiAnalysis.decision === 'BUY' ? "bg-success" : "bg-destructive"
                )}>
                  <div className={cn(
                    "absolute inset-0 rounded-full animate-ping opacity-75",
                    aiAnalysis.decision === 'BUY' ? "bg-success" : "bg-destructive"
                  )} />
                </div>
                <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Chartor Says
                </span>
              </div>
              <div className={cn(
                "flex items-center gap-1 px-2 py-1 rounded-full text-xs font-mono",
                aiAnalysis.decision === 'BUY' ? "bg-success/20 text-success" : "bg-destructive/20 text-destructive"
              )}>
                <Zap className="w-3 h-3" />
                {aiAnalysis.confidence}%
              </div>
            </div>

            {/* Signal Type */}
            <div className="flex items-center gap-3 mb-4">
              <div className={cn(
                "w-12 h-12 rounded-xl flex items-center justify-center",
                aiAnalysis.decision === 'BUY' ? "bg-success/20" : "bg-destructive/20"
              )}>
                {aiAnalysis.decision === 'BUY' ? (
                  <TrendingUp className={cn("w-6 h-6 text-success")} />
                ) : (
                  <TrendingDown className={cn("w-6 h-6 text-destructive")} />
                )}
              </div>
              <div>
                <div className={cn(
                  "text-xl font-bold",
                  aiAnalysis.decision === 'BUY' ? "text-success" : "text-destructive"
                )}>
                  {aiAnalysis.decision} {asset.symbol}
                </div>
                <div className="text-sm text-muted-foreground">
                  Confidence: {aiAnalysis.confidence}%
                </div>
              </div>
            </div>

            {/* Market Metrics */}
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="bg-background/50 rounded-lg p-2 text-center">
                <div className="text-[10px] text-muted-foreground uppercase">Price</div>
                <div className="text-sm font-mono text-foreground">{aiAnalysis.price ? formatPrice(aiAnalysis.price) : 'N/A'}</div>
              </div>
              <div className="bg-background/50 rounded-lg p-2 text-center">
                <div className="text-[10px] text-muted-foreground uppercase">RSI</div>
                <div className="text-sm font-mono text-foreground">{aiAnalysis.rsi ? aiAnalysis.rsi.toFixed(1) : 'N/A'}</div>
              </div>
              <div className="bg-background/50 rounded-lg p-2 text-center">
                <div className="text-[10px] text-muted-foreground uppercase">Trend</div>
                <div className="text-sm font-mono text-foreground">{aiAnalysis.trend || 'N/A'}</div>
              </div>
            </div>

            {/* AI Reasoning */}
            <div className="bg-background/50 rounded-lg p-3 mb-4">
              <div className="text-[10px] text-muted-foreground uppercase mb-1 flex items-center gap-1">
                <Brain className="w-3 h-3" />
                AI Reasoning
              </div>
              <div className="text-xs text-foreground leading-relaxed">
                {aiAnalysis.reasoning}
              </div>
            </div>

            {/* Timestamp */}
            <div className="flex items-center justify-center gap-1 text-[10px] text-muted-foreground/60 mb-3">
              <Clock className="w-3 h-3" />
              {formatTimestamp(aiAnalysis.timestamp)}
            </div>

            {/* Status & Action */}
            {autoTrading ? (
              <div className="text-center text-sm text-success font-medium mb-4 animate-pulse">
                Auto-executing based on risk tolerance...
              </div>
            ) : (
              <>
                <div className="text-center text-sm text-muted-foreground mb-4">
                  Awaiting your authorization...
                </div>
                <Button
                  variant={aiAnalysis.decision === 'BUY' ? 'long' : 'short'}
                  size="xl"
                  onClick={() => handleAuthorizeTrade(aiAnalysis.decision)}
                  className="w-full animate-scale-in"
                >
                  <Power className="w-5 h-5" />
                  AUTHORIZE {aiAnalysis.decision}
                </Button>
              </>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4">
              <Shield className="w-8 h-8 text-muted-foreground/50" />
            </div>
            <div className="text-sm font-medium text-muted-foreground mb-1">
              No Analysis Available
            </div>
            <div className="text-xs text-muted-foreground/60 mb-4">
              Click below to analyze {asset.symbol}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={triggerAnalysis}
              className="gap-2"
            >
              <Brain className="w-4 h-4" />
              Analyze Now
            </Button>
          </div>
        )}
      </div>

      {/* Emergency Controls */}
      <div className="p-4 border-t border-border bg-card/50">
        <div className="flex items-center gap-2 mb-3">
          <AlertTriangle className="w-3.5 h-3.5 text-warning" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Emergency Controls
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={onForceClose}
          className="w-full border-destructive/30 text-destructive hover:bg-destructive/10 hover:text-destructive"
        >
          <XCircle className="w-4 h-4" />
          Force Liquidate (Close All)
        </Button>
      </div>
    </div>
  );
}
