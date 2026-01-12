import { cn } from "@/lib/utils";
import { Shield, Target, Activity, DollarSign, BarChart3 } from "lucide-react";
import { TradingMode } from "@/types/trading";

interface TopNavbarProps {
  tradingMode: TradingMode;
  onModeChange: (mode: TradingMode) => void;
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function TopNavbar({ tradingMode, onModeChange, activeTab, onTabChange }: TopNavbarProps) {
  const navItems = [
    { id: "sentinel", label: "Sentinel", icon: Shield },
    { id: "strategies", label: "Strategy Market", icon: Target },
    { id: "trade", label: "Trade", icon: Activity },
    { id: "positions", label: "Positions", icon: DollarSign },
    { id: "metrics", label: "Metrics", icon: BarChart3 },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 h-16 bg-[#111] border-b border-[#1f1f22] z-50">
      <div className="max-w-[1600px] mx-auto h-full flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center">
            <img
              src="/ChartorLogo.png"
              alt="Chartor"
              className="h-8 w-auto object-contain invert brightness-0"
            />
            <h1 className="text-2xl font-bold text-white tracking-tight">
              hartor
            </h1>
          </div>

          <div className="hidden md:flex items-center">
            <div className="flex gap-1 p-1 bg-[#1f1f22] rounded-lg border border-[#27272a]">
              {(['scalping', 'intraday', 'swing', 'institutional'] as TradingMode[]).map((mode) => {
                const isActive = tradingMode === mode;
                const labels = {
                  scalping: '1m',
                  intraday: '15m',
                  swing: '4h',
                  institutional: 'Quant'
                } as Record<TradingMode, string>;
                return (
                  <button
                    key={mode}
                    onClick={() => onModeChange(mode)}
                    className={cn(
                      "px-3 py-1 rounded text-xs font-medium transition-colors",
                      isActive
                        ? mode === 'institutional'
                          ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white"
                          : "bg-primary text-white"
                        : "text-[#888] hover:text-white hover:bg-[#27272a]"
                    )}
                  >
                    {labels[mode]}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <nav className="flex items-center gap-1 flex-1 justify-end mr-8">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onTabChange(item.id)}
                className={cn(
                  "px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2",
                  isActive
                    ? "text-white bg-[#1f1f22]"
                    : "text-[#888] hover:text-white hover:bg-[#1a1a1a]"
                )}
              >
                <Icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

