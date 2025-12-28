import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown, DollarSign, X, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Position {
  id: number;
  symbol: string;
  side: string;
  size: number;
  entry_price: number;
  current_price: number | null;
  unrealized_pnl: number | null;
  leverage: number;
  opened_at: string;
}

export function PositionsTab() {
  const [positions, setPositions] = useState<Position[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [totalUnrealizedPnL, setTotalUnrealizedPnL] = useState(0);

  useEffect(() => {
    fetchPositions();
    const interval = setInterval(fetchPositions, 5000); // Refresh every 5s
    return () => clearInterval(interval);
  }, []);

  const fetchPositions = async () => {
    try {
      const response = await fetch("/api/positions");
      const data = await response.json();
      
      if (data.status === "success" && data.positions) {
        setPositions(data.positions);
        const total = data.positions.reduce((sum: number, p: Position) => 
          sum + (p.unrealized_pnl || 0), 0
        );
        setTotalUnrealizedPnL(total);
      }
      setIsLoading(false);
    } catch (error) {
      console.error("Failed to fetch positions:", error);
      setIsLoading(false);
    }
  };

  const closePosition = async (symbol: string, side: string) => {
    try {
      // This would call an API endpoint to close the position
      // For now, we'll just show a message
      const response = await fetch("/api/close-position", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, side })
      });
      
      const result = await response.json();
      if (result.status === "success") {
        fetchPositions(); // Refresh
      }
    } catch (error) {
      console.error("Failed to close position:", error);
    }
  };

  const formatPrice = (price: number | null) => {
    if (!price) return "N/A";
    if (price >= 1000) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (price >= 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(4)}`;
  };

  const getSymbolDisplay = (symbol: string) => {
    return symbol.replace("cmt_", "").replace("usdt", "").toUpperCase();
  };

  const calculatePnLPercent = (entry: number, current: number | null, side: string) => {
    if (!current || entry === 0) return 0;
    const change = side === "buy" 
      ? ((current - entry) / entry) * 100
      : ((entry - current) / entry) * 100;
    return Math.round(change * 100) / 100;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-foreground">Open Positions</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={fetchPositions}
            className="h-6 w-6 p-0"
          >
            <RefreshCw className="w-3 h-3" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">Current positions and unrealized P&L</p>
      </div>

      {/* Total P&L Summary */}
      <div className="p-4 border-b border-border bg-card/50">
        <div className="bg-background/50 rounded-lg p-3 text-center">
          <div className="text-[10px] text-muted-foreground uppercase mb-1">Total Unrealized P&L</div>
          <div className={cn(
            "text-2xl font-mono font-bold",
            totalUnrealizedPnL >= 0 ? "text-success" : "text-destructive"
          )}>
            {totalUnrealizedPnL >= 0 ? '+' : ''}{formatPrice(totalUnrealizedPnL)}
          </div>
        </div>
      </div>

      {/* Positions List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4 animate-pulse">
              <DollarSign className="w-8 h-8 text-muted-foreground/50" />
            </div>
            <div className="text-sm font-medium text-muted-foreground mb-1">
              Loading Positions...
            </div>
          </div>
        ) : positions.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <DollarSign className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
            <div className="text-sm font-medium text-muted-foreground mb-1">
              No Open Positions
            </div>
            <div className="text-xs text-muted-foreground/60">
              Your open positions will appear here
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {positions.map((position) => {
              const pnlPercent = calculatePnLPercent(position.entry_price, position.current_price, position.side);
              
              return (
                <div
                  key={position.id}
                  className={cn(
                    "rounded-lg p-4 border transition-all hover:bg-card/50",
                    position.side === "buy" 
                      ? "border-success/20 bg-success/5" 
                      : "border-destructive/20 bg-destructive/5"
                  )}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {position.side === "buy" ? (
                        <TrendingUp className="w-5 h-5 text-success" />
                      ) : (
                        <TrendingDown className="w-5 h-5 text-destructive" />
                      )}
                      <div>
                        <div className="text-sm font-bold text-foreground">
                          {getSymbolDisplay(position.symbol)}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {position.side.toUpperCase()} • {position.size} @ {formatPrice(position.entry_price)}
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => closePosition(position.symbol, position.side)}
                      className="h-7 w-7 p-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-background/50 rounded p-2">
                      <div className="text-[10px] text-muted-foreground uppercase mb-1">Entry</div>
                      <div className="text-sm font-mono text-foreground">{formatPrice(position.entry_price)}</div>
                    </div>
                    <div className="bg-background/50 rounded p-2">
                      <div className="text-[10px] text-muted-foreground uppercase mb-1">Current</div>
                      <div className="text-sm font-mono text-foreground">{formatPrice(position.current_price)}</div>
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-[10px] text-muted-foreground uppercase">Unrealized P&L</div>
                      <div className={cn(
                        "text-lg font-mono font-bold",
                        (position.unrealized_pnl || 0) >= 0 ? "text-success" : "text-destructive"
                      )}>
                        {(position.unrealized_pnl || 0) >= 0 ? '+' : ''}{formatPrice(position.unrealized_pnl)}
                      </div>
                      <div className={cn(
                        "text-xs font-mono",
                        pnlPercent >= 0 ? "text-success" : "text-destructive"
                      )}>
                        {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                      </div>
                    </div>
                    {position.leverage > 1 && (
                      <div className="text-right">
                        <div className="text-[10px] text-muted-foreground uppercase">Leverage</div>
                        <div className="text-sm font-mono font-bold text-warning">
                          {position.leverage}x
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

