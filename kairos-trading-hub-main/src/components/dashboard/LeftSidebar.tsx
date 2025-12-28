import { TradingMode, Asset } from "@/types/trading";
import { TradingModeSelector } from "./TradingModeSelector";
import { AssetWatchlist } from "./AssetWatchlist";
import { Activity, Zap } from "lucide-react";

interface LeftSidebarProps {
  tradingMode: TradingMode;
  onModeChange: (mode: TradingMode) => void;
  assets: Asset[];
  selectedAsset: string;
  onAssetSelect: (symbol: string) => void;
  isLoading?: boolean;
}

export function LeftSidebar({
  tradingMode,
  onModeChange,
  assets,
  selectedAsset,
  onAssetSelect,
  isLoading = false,
}: LeftSidebarProps) {
  return (
    <aside className="w-72 h-full flex flex-col bg-sidebar border-r border-border">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Zap className="w-6 h-6 text-primary" />
          </div>
          <h1 className="text-xl font-bold font-mono tracking-tight text-foreground">
            CHARTOR
          </h1>
          <div className="ml-auto flex items-center gap-2">
            <div className="relative w-2.5 h-2.5">
              <div className="absolute inset-0 rounded-full bg-success animate-ping opacity-75" />
              <div className="relative w-2.5 h-2.5 rounded-full bg-success" />
            </div>
            <span className="text-xs text-muted-foreground">LIVE</span>
          </div>
        </div>
      </div>

      {/* Trading Mode Selector */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Activity className="w-4 h-4 text-muted-foreground" />
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Trading Mode
          </span>
        </div>
        <TradingModeSelector activeMode={tradingMode} onModeChange={onModeChange} />
      </div>

      {/* Asset Watchlist */}
      <div className="flex-1 overflow-hidden flex flex-col p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
            Watchlist
          </span>
          <span className="text-xs text-muted-foreground">{assets.length} assets</span>
        </div>
        <div className="flex-1 overflow-y-auto scrollbar-thin -mx-2 px-2">
          <AssetWatchlist
            assets={assets}
            selectedAsset={selectedAsset}
            onAssetSelect={onAssetSelect}
            isLoading={isLoading}
          />
        </div>
      </div>
    </aside>
  );
}
