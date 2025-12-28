import { Button } from "@/components/ui/button";
import { TradingMode, TRADING_MODES } from "@/types/trading";
import { cn } from "@/lib/utils";

interface TradingModeSelectorProps {
  activeMode: TradingMode;
  onModeChange: (mode: TradingMode) => void;
}

export function TradingModeSelector({ activeMode, onModeChange }: TradingModeSelectorProps) {
  const modes = Object.entries(TRADING_MODES) as [TradingMode, typeof TRADING_MODES[TradingMode]][];

  return (
    <div className="flex gap-1 p-1 bg-secondary/50 rounded-lg border border-border">
      {modes.map(([mode, config]) => {
        const isActive = activeMode === mode;
        const variantMap: Record<TradingMode, "modeScalping" | "modeIntraday" | "modeSwing"> = {
          scalping: "modeScalping",
          intraday: "modeIntraday",
          swing: "modeSwing",
        };

        return (
          <Button
            key={mode}
            variant={isActive ? variantMap[mode] : "mode"}
            size="sm"
            onClick={() => onModeChange(mode)}
            className={cn(
              "flex-1 text-xs font-medium transition-all duration-200",
              isActive && "shadow-lg"
            )}
          >
            <span className="flex flex-col items-center gap-0.5">
              <span>{config.label}</span>
              <span className="text-[10px] opacity-70">{config.timeframes}</span>
            </span>
          </Button>
        );
      })}
    </div>
  );
}
