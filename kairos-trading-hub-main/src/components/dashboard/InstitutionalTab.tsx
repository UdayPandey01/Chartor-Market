import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { TrendingUp, Activity, Shield, Target, BarChart3, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getApiUrl } from "@/lib/api";

interface InstitutionalMetrics {
    total_signals: number;
    trades_executed: number;
    signals_filtered_regime: number;
    signals_filtered_risk: number;
    current_regime?: string;
    portfolio_exposure?: number;
    active_positions?: number;
}

export function InstitutionalTab() {
    const [isActive, setIsActive] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [metrics, setMetrics] = useState<InstitutionalMetrics>({
        total_signals: 0,
        trades_executed: 0,
        signals_filtered_regime: 0,
        signals_filtered_risk: 0,
    });

    useEffect(() => {
        checkStatus();
        const interval = setInterval(checkStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    const checkStatus = async () => {
        try {
            const response = await fetch(getApiUrl("/api/institutional/status"));
            const data = await response.json();

            if (data.status === "success") {
                setIsActive(data.running || false);

                // Fetch metrics if running
                if (data.running) {
                    // This would need a metrics endpoint - placeholder for now
                    // fetchMetrics();
                }
            }
        } catch (error) {
            console.error("Failed to check institutional status:", error);
        }
    };

    const toggleInstitutional = async () => {
        setIsLoading(true);
        try {
            const endpoint = isActive ? "/api/institutional/stop" : "/api/institutional/start";
            const response = await fetch(getApiUrl(endpoint), { method: "POST" });
            const data = await response.json();

            if (data.status === "success") {
                setIsActive(!isActive);
            } else {
                alert(data.msg || "Failed to toggle institutional trading");
            }
        } catch (error) {
            console.error("Failed to toggle institutional:", error);
            alert("Failed to toggle institutional trading");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="p-6 space-y-6">
            {/* Header with Toggle */}
            <div className="flex items-center justify-between pb-4 border-b border-border/50">
                <div>
                    <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center">
                            <BarChart3 className="w-4 h-4 text-white" />
                        </div>
                        Institutional Quant
                    </h2>
                    <p className="text-xs text-muted-foreground mt-1">
                        Multi-asset momentum with regime detection
                    </p>
                </div>
                <Switch
                    checked={isActive}
                    onCheckedChange={toggleInstitutional}
                    disabled={isLoading}
                    className="data-[state=checked]:bg-gradient-to-r data-[state=checked]:from-purple-600 data-[state=checked]:to-indigo-600"
                />
            </div>

            {/* Status Banner */}
            <div
                className={cn(
                    "p-4 rounded-lg border",
                    isActive
                        ? "bg-gradient-to-r from-purple-500/10 to-indigo-500/10 border-purple-500/30"
                        : "bg-muted/50 border-border/50"
                )}
            >
                <div className="flex items-center gap-3">
                    <div
                        className={cn(
                            "w-3 h-3 rounded-full animate-pulse",
                            isActive ? "bg-purple-500" : "bg-muted-foreground/50"
                        )}
                    />
                    <div className="flex-1">
                        <p className="text-sm font-medium text-foreground">
                            {isActive ? "System Active" : "System Idle"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                            {isActive
                                ? "Scanning markets every 30 seconds for opportunities"
                                : "Enable to start multi-asset rotation trading"}
                        </p>
                    </div>
                </div>
            </div>

            {/* System Overview */}
            <div className="space-y-3">
                <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide flex items-center gap-2">
                    <Activity className="w-4 h-4" />
                    System Components
                </h3>

                <div className="grid grid-cols-1 gap-3">
                    {/* Strategy Engine */}
                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-blue-500/10 flex items-center justify-center">
                                <TrendingUp className="w-4 h-4 text-blue-500" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-foreground">Intraday Momentum</p>
                                <p className="text-xs text-muted-foreground truncate">
                                    RSI + Bollinger + EMA signals
                                </p>
                            </div>
                            <div className={cn(
                                "px-2 py-1 rounded text-xs font-medium",
                                isActive ? "bg-green-500/20 text-green-400" : "bg-muted text-muted-foreground"
                            )}>
                                {isActive ? "ACTIVE" : "IDLE"}
                            </div>
                        </div>
                    </div>

                    {/* Regime Detector */}
                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
                                <Target className="w-4 h-4 text-purple-500" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-foreground">OFRAS Regime</p>
                                <p className="text-xs text-muted-foreground truncate">
                                    Market state classification
                                </p>
                            </div>
                            <div className={cn(
                                "px-2 py-1 rounded text-xs font-medium",
                                isActive ? "bg-green-500/20 text-green-400" : "bg-muted text-muted-foreground"
                            )}>
                                {isActive ? "ACTIVE" : "IDLE"}
                            </div>
                        </div>
                    </div>

                    {/* Risk Manager */}
                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
                                <Shield className="w-4 h-4 text-red-500" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-foreground">Risk Manager</p>
                                <p className="text-xs text-muted-foreground truncate">
                                    1.25% risk per trade, 40% max exposure
                                </p>
                            </div>
                            <div className={cn(
                                "px-2 py-1 rounded text-xs font-medium",
                                isActive ? "bg-green-500/20 text-green-400" : "bg-muted text-muted-foreground"
                            )}>
                                {isActive ? "ACTIVE" : "IDLE"}
                            </div>
                        </div>
                    </div>

                    {/* Execution Engine */}
                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center">
                                <Zap className="w-4 h-4 text-green-500" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-foreground">Execution Engine</p>
                                <p className="text-xs text-muted-foreground truncate">
                                    Slippage control + partial fills
                                </p>
                            </div>
                            <div className={cn(
                                "px-2 py-1 rounded text-xs font-medium",
                                isActive ? "bg-green-500/20 text-green-400" : "bg-muted text-muted-foreground"
                            )}>
                                {isActive ? "ACTIVE" : "IDLE"}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Performance Metrics */}
            <div className="space-y-3">
                <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide">
                    Performance Metrics
                </h3>

                <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-xs text-muted-foreground mb-1">Total Signals</p>
                        <p className="text-2xl font-bold text-foreground">{metrics.total_signals}</p>
                    </div>

                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-xs text-muted-foreground mb-1">Trades Executed</p>
                        <p className="text-2xl font-bold text-foreground">{metrics.trades_executed}</p>
                    </div>

                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-xs text-muted-foreground mb-1">Regime Filter</p>
                        <p className="text-2xl font-bold text-foreground">{metrics.signals_filtered_regime}</p>
                    </div>

                    <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-xs text-muted-foreground mb-1">Risk Filter</p>
                        <p className="text-2xl font-bold text-foreground">{metrics.signals_filtered_risk}</p>
                    </div>
                </div>
            </div>

            {/* Asset Universe */}
            <div className="space-y-3">
                <h3 className="text-sm font-semibold text-foreground uppercase tracking-wide">
                    Asset Universe
                </h3>

                <div className="grid grid-cols-4 gap-2">
                    {["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "BNB", "LTC"].map((symbol) => (
                        <div
                            key={symbol}
                            className="p-2 rounded-lg bg-muted/30 border border-border/50 text-center"
                        >
                            <p className="text-xs font-medium text-foreground">{symbol}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Info Card */}
            <div className="p-4 rounded-lg bg-gradient-to-r from-purple-500/5 to-indigo-500/5 border border-purple-500/20">
                <p className="text-xs text-muted-foreground leading-relaxed">
                    <span className="font-semibold text-foreground">How it works:</span> The system scans all 8 assets every 30 seconds,
                    scores opportunities based on momentum + regime fit, then rotates capital to the highest probability trade.
                    Risk management ensures 1.25% risk per trade with strict portfolio limits.
                </p>
            </div>

            {/* Action Buttons */}
            {isActive && (
                <div className="flex gap-2">
                    <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => window.open('/logs', '_blank')}
                    >
                        View Logs
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        className="flex-1"
                        onClick={() => alert('Backtest feature coming soon')}
                    >
                        Run Backtest
                    </Button>
                </div>
            )}
        </div>
    );
}
