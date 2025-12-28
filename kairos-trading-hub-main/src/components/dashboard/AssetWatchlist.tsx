import { Asset } from "@/types/trading";
import { cn } from "@/lib/utils";
import { TrendingUp, TrendingDown } from "lucide-react";

interface AssetWatchlistProps {
  assets: Asset[];
  selectedAsset: string;
  onAssetSelect: (symbol: string) => void;
  isLoading?: boolean;
}

export function AssetWatchlist({ assets, selectedAsset, onAssetSelect, isLoading = false }: AssetWatchlistProps) {
  const formatPrice = (price: number) => {
    if (price >= 1000) return `$${price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    if (price >= 1) return `$${price.toFixed(2)}`;
    return `$${price.toFixed(4)}`;
  };

  const formatChange = (change: number) => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(2)}%`;
  };

  // Skeleton loader
  if (isLoading || assets.length === 0) {
    return (
      <div className="flex flex-col gap-1">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="flex items-center gap-3 p-3 rounded-lg border border-border animate-pulse">
            <div className="w-8 h-8 rounded-full bg-muted" />
            <div className="flex-1 min-w-0">
              <div className="h-4 bg-muted rounded w-12 mb-1" />
              <div className="h-3 bg-muted rounded w-20" />
            </div>
            <div className="text-right">
              <div className="h-4 bg-muted rounded w-16 mb-1" />
              <div className="h-3 bg-muted rounded w-12" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1">
      {assets.map((asset) => {
        const isSelected = selectedAsset === asset.symbol;
        const isPositive = asset.change24h >= 0;

        return (
          <button
            key={asset.symbol}
            onClick={() => onAssetSelect(asset.symbol)}
            className={cn(
              "flex items-center gap-3 p-3 rounded-lg transition-all duration-200 text-left",
              "hover:bg-muted/50 border border-transparent",
              isSelected && "glass border-primary/30"
            )}
          >
            {/* Token Icon */}
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center font-mono font-semibold text-xs",
              isSelected ? "bg-primary/30 text-primary" : "bg-muted text-muted-foreground"
            )}>
              {asset.symbol.charAt(0)}
            </div>

            {/* Symbol & Pair */}
            <div className="flex-1 min-w-0">
              <div className="font-medium text-foreground text-sm">{asset.symbol}</div>
              <div className="text-xs text-muted-foreground truncate">{asset.pair}</div>
            </div>

            {/* Price & Change */}
            <div className="text-right">
              <div className="font-mono text-sm text-foreground">
                {formatPrice(asset.price)}
              </div>
              <div className={cn(
                "flex items-center justify-end gap-1 text-xs font-mono",
                isPositive ? "text-success" : "text-destructive"
              )}>
                {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {formatChange(asset.change24h)}
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}
