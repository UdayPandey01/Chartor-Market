import { useState, useEffect } from "react";
import { TopNavbar } from "@/components/dashboard/TopNavbar";
import { ChartPanel } from "@/components/dashboard/ChartPanel";
import { TerminalLog } from "@/components/dashboard/TerminalLog";
import { FloatingChat } from "@/components/dashboard/FloatingChat";
import { MarketTicker } from "@/components/dashboard/MarketTicker";
import { SentinelControlTab } from "@/components/dashboard/SentinelControlTab";
import { StrategiesTab } from "@/components/dashboard/StrategiesTab";
import { TradesHistoryTab } from "@/components/dashboard/TradesHistoryTab";
import { PositionsTab } from "@/components/dashboard/PositionsTab";
import { RiskMetricsTab } from "@/components/dashboard/RiskMetricsTab";
import { InstitutionalTab } from "@/components/dashboard/InstitutionalTab";
import { Asset, TradingMode, LogEntry, ChatMessage } from "@/types/trading";
import { toast } from "@/hooks/use-toast";
import { getApiUrl } from "@/lib/api";

const INITIAL_LOGS: LogEntry[] = [
  { id: '1', timestamp: new Date(Date.now() - 5000), type: 'system', message: 'CHARTOR v2.4.1 initialized successfully' },
  { id: '2', timestamp: new Date(Date.now() - 4000), type: 'sentinel', message: 'Connecting to market data feeds...' },
  { id: '3', timestamp: new Date(Date.now() - 3000), type: 'risk', message: 'Leverage cap enforced: 20x maximum' },
];

const Index = () => {
  // 1. State Management
  const [tradingMode, setTradingMode] = useState<TradingMode>('intraday');
  const [selectedAsset, setSelectedAsset] = useState('BTC'); // Default UI Selection
  const [activeSymbol, setActiveSymbol] = useState("cmt_btcusdt"); // Default API Symbol
  const [activeTab, setActiveTab] = useState("sentinel"); // Top nav active tab

  const [assets, setAssets] = useState<Asset[]>([]);
  const [isLoadingAssets, setIsLoadingAssets] = useState(true);

  const [logs, setLogs] = useState<LogEntry[]>(INITIAL_LOGS);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chartData, setChartData] = useState([]);

  // Helper to find current asset details (Icon, etc.) from your mock list
  const currentAsset = assets.find(a => a.symbol === selectedAsset) || assets[0] || {
    symbol: selectedAsset,
    pair: `${selectedAsset}/USDT`,
    price: 0,
    change24h: 0,
    volume24h: 0,
    high24h: 0,
    low24h: 0,
  };

  // 1.5 Live Watchlist (Sidebar) Fetch
  useEffect(() => {
    const fetchWatchlist = async () => {
      try {
        const response = await fetch(getApiUrl('/api/watchlist'));
        if (!response.ok) throw new Error('Watchlist offline');

        const data = await response.json();
        const mapped: Asset[] = (Array.isArray(data) ? data : []).map((item: Record<string, unknown>) => {
          const pair = typeof item?.symbol === 'string' ? item.symbol : 'UNKNOWN/USDT';
          const symbol = pair.split('/')[0] || 'UNKNOWN';
          const price = Number(item?.price ?? 0);
          const change24h = Number(item?.change ?? 0);
          const volume24h = Number(item?.volume24h ?? 0);
          const high24h = Number(item?.high24h ?? 0);
          const low24h = Number(item?.low24h ?? 0);

          return {
            symbol,
            pair,
            price,
            change24h,
            volume24h,
            high24h,
            low24h,
            raw_symbol: typeof item?.raw_symbol === 'string' ? item.raw_symbol : undefined,
          };
        });

        if (mapped.length > 0) {
          setAssets(mapped);
          setIsLoadingAssets(false);
        }
      } catch {
        // On error, keep loading state or use fallback
        setIsLoadingAssets(false);
      }
    };

    fetchWatchlist();
    const interval = setInterval(fetchWatchlist, 5000);
    return () => clearInterval(interval);
  }, []);

  // 2. Real-Time Chart Data Fetching
  useEffect(() => {
    const fetchCandles = async () => {
      // Skip chart fetch for institutional mode - it shows metrics instead
      if (tradingMode === 'institutional') {
        return;
      }

      try {
        // Map Trading Mode to Interval
        let interval = "15m";
        if (tradingMode === 'scalping') interval = "1m";
        if (tradingMode === 'swing') interval = "4h";

        // console.log("Fetching candles for:", activeSymbol);
        const response = await fetch(getApiUrl(`/api/candles?symbol=${activeSymbol}&interval=${interval}`));
        if (!response.ok) throw new Error("API Offline");

        const data = await response.json();
        setChartData(data); // <--- Updates the Chart
      } catch (error) {
        console.error("Error loading chart:", error);
        // Optional: Add a log entry if connection fails
      }
    };

    fetchCandles();
    const interval = setInterval(fetchCandles, 5000); // Poll every 5s
    return () => clearInterval(interval);
  }, [activeSymbol, tradingMode]);

  // 3. Handlers
  const handleModeChange = (mode: TradingMode) => {
    setTradingMode(mode);

    // Auto-switch to sentinel tab when institutional mode is selected
    if (mode === 'institutional' && activeTab !== 'sentinel') {
      setActiveTab('sentinel');
    }

    addLog('system', `Trading mode switched to ${mode.toUpperCase()}`);
    addLog('system', `Trading mode switched to ${mode.toUpperCase()}`);
  };

  const handleAssetSelect = async (symbol: string) => {
    // 1. Update UI State
    setSelectedAsset(symbol);

    // 2. Map UI Symbol (BTC) to API Symbol (cmt_btcusdt)
    // Note: WEEX Futures symbols usually follow 'cmt_symbolusdt' format
    const apiSymbol = `cmt_${symbol.toLowerCase()}usdt`;
    setActiveSymbol(apiSymbol);

    // 3. Update current_symbol in database so sentinel uses the correct asset
    try {
      await fetch(getApiUrl("/api/trade-settings"), {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          current_symbol: apiSymbol
        })
      });
      console.log(`Updated sentinel symbol to: ${apiSymbol}`);
    } catch (error) {
      console.error("Failed to update current symbol:", error);
    }

    addLog('sentinel', `Asset focus changed to ${symbol}/USDT`);
  };

  const handleSendMessage = async (content: string) => {
    // 1. Add User Message immediately
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: new Date(),
    };
    setChatMessages(prev => [...prev, userMessage]);

    // 2. Call Python Backend (Real AI)
    try {
      const response = await fetch(getApiUrl('/api/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: content })
      });
      const data = await response.json();

      // 3. Add AI Response
      const aiMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: (data && typeof data.response === 'string' && data.response.trim().length > 0)
          ? data.response
          : 'Chartor: No response received from the backend.',
        timestamp: new Date(),
      };
      setChatMessages(prev => [...prev, aiMessage]);

    } catch (error) {
      const fallbackMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'Chartor (offline): Unable to reach the backend at /api/chat. Make sure FastAPI is running on port 8000.',
        timestamp: new Date(),
      };
      setChatMessages(prev => [...prev, fallbackMessage]);
      toast({ title: "AI Error", description: "Could not connect to Chartor Brain.", variant: "destructive" });
    }
  };

  const handleAuthorizeTrade = async (type: 'long' | 'short') => {
    // 1. Execute Real Trade on Backend
    try {
      const action = type === 'long' ? 'buy' : 'sell';

      // Optimistic UI Update
      toast({ title: "Sending Order...", description: `Executing ${action.toUpperCase()} on ${selectedAsset}...` });

      const response = await fetch(getApiUrl(`/api/trade?action=${action}`), {
        method: 'POST'
      });
      const result = await response.json();

      if (result.status === "success") {
        addLog('trade', `AUTHORIZED: ${type.toUpperCase()} executed. ID: ${Date.now()}`);
        toast({
          title: "Order Filled",
          description: `${type.toUpperCase()} ${selectedAsset} - Success`,
          variant: "default"
        });
      } else {
        throw new Error(result.msg || "Unknown error");
      }

    } catch (error) {
      addLog('risk', `Trade Failed: ${error}`);
      toast({ title: "Execution Failed", description: "Check API Logs.", variant: "destructive" });
    }
  };

  const handleForceClose = async () => {
    try {
      addLog('risk', 'EMERGENCY: Force liquidation triggered');
      toast({ title: 'Force Liquidation', description: 'Closing all positions...', variant: 'destructive' });

      const response = await fetch(getApiUrl("/api/force-close"), {
        method: "POST"
      });

      const result = await response.json();

      if (result.status === "success") {
        addLog('trade', `Force close completed: ${result.closed} positions closed`);
        toast({
          title: "Force Close Complete",
          description: `${result.closed} positions closed successfully`,
          variant: "default"
        });
      } else {
        throw new Error(result.msg || "Force close failed");
      }
    } catch (error) {
      addLog('risk', `Force close failed: ${error}`);
      toast({
        title: "Force Close Failed",
        description: "Could not close all positions. Check logs.",
        variant: "destructive"
      });
    }
  };

  // Helper to append logs easily
  const addLog = (type: LogEntry['type'], message: string) => {
    setLogs(prev => [...prev.slice(-50), {
      id: Date.now().toString(),
      timestamp: new Date(),
      type,
      message
    }]);
  };

  // Fetch real logs from API
  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await fetch(getApiUrl("/api/logs?limit=20"));
        if (response.ok) {
          const apiLogs = await response.json();
          if (Array.isArray(apiLogs) && apiLogs.length > 0) {
            // Convert API logs to LogEntry format
            const formattedLogs: LogEntry[] = apiLogs.map((log: any) => ({
              id: log.id || Date.now().toString(),
              timestamp: new Date(log.timestamp),
              type: log.type || 'system',
              message: log.message || 'No message'
            }));

            // Merge with existing logs, avoiding duplicates
            setLogs(prev => {
              const existingIds = new Set(prev.map(l => l.id));
              const newLogs = formattedLogs.filter((l: LogEntry) => !existingIds.has(l.id));
              return [...prev, ...newLogs].slice(-50); // Keep last 50 logs
            });
          }
        }
      } catch (error) {
        console.error("Failed to fetch logs:", error);
      }
    };

    // Fetch logs immediately and then every 5 seconds
    fetchLogs();
    const interval = setInterval(fetchLogs, 5000);
    return () => clearInterval(interval);
  }, []);

  // Render active tab content
  const renderTabContent = () => {
    // Special case: If institutional mode, always show institutional tab
    if (tradingMode === 'institutional') {
      return <InstitutionalTab />;
    }

    switch (activeTab) {
      case "sentinel":
        return (
          <SentinelControlTab
            asset={currentAsset}
            onAuthorizeTrade={handleAuthorizeTrade}
            onForceClose={handleForceClose}
          />
        );
      case "strategies":
        return <StrategiesTab />;
      case "trade":
        return <TradesHistoryTab />;
      case "positions":
        return <PositionsTab />;
      case "metrics":
        return <RiskMetricsTab />;
      default:
        return (
          <SentinelControlTab
            asset={currentAsset}
            onAuthorizeTrade={handleAuthorizeTrade}
            onForceClose={handleForceClose}
          />
        );
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#09090b]">
      {/* Top Navigation Bar */}
      <TopNavbar
        tradingMode={tradingMode}
        onModeChange={handleModeChange}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Main Content Area - Below Navbar */}
      <div className="pt-16 pb-6">
        <div className="max-w-[1600px] mx-auto px-6 py-6">
          <div className="grid grid-cols-12 gap-6">
            {/* Left Column - Chart or Institutional Dashboard (75% / 9 columns) */}
            <div className="col-span-12 lg:col-span-9 flex flex-col gap-4">
              {tradingMode === 'institutional' ? (
                // Institutional Mode: Show multi-asset overview instead of single chart
                <div className="bg-[#111] rounded-3xl border border-[#1f1f22] p-6">
                  <div className="mb-4 pb-4 border-b border-border/50">
                    <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center">
                        <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                        </svg>
                      </div>
                      Multi-Asset Performance Dashboard
                    </h2>
                    <p className="text-xs text-muted-foreground mt-1">
                      Real-time monitoring of 8-asset quant system
                    </p>
                  </div>

                  <div className="grid grid-cols-4 gap-4">
                    {assets.slice(0, 8).map((asset) => (
                      <div
                        key={asset.symbol}
                        className="p-4 rounded-lg bg-muted/30 border border-border/50 hover:bg-muted/50 transition-all cursor-pointer"
                        onClick={() => handleAssetSelect(asset.symbol)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm font-bold text-foreground">{asset.symbol}</span>
                          <span className={`text-xs font-medium ${asset.change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {asset.change24h >= 0 ? '↑' : '↓'} {Math.abs(asset.change24h).toFixed(2)}%
                          </span>
                        </div>
                        <div className="text-lg font-bold text-foreground mb-1">
                          ${asset.price.toLocaleString()}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          Vol: ${(asset.volume24h / 1000000).toFixed(0)}M
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="mt-6 p-4 rounded-lg bg-gradient-to-r from-purple-500/10 to-indigo-500/10 border border-purple-500/20">
                    <p className="text-sm text-muted-foreground">
                      <span className="font-semibold text-foreground">System Status:</span> The institutional quant system scans all assets every 30 seconds,
                      ranks them by momentum + regime fit, and automatically rotates capital to the highest probability opportunity.
                      Enable the system in the control panel on the right →
                    </p>
                  </div>
                </div>
              ) : (
                // Standard Mode: Show single asset chart
                <ChartPanel
                  asset={currentAsset}
                  tradingMode={tradingMode}
                  data={chartData}
                />
              )}

              <div className="bg-[#111] rounded-3xl border border-[#1f1f22] overflow-hidden">
                <TerminalLog logs={logs} />
              </div>
            </div>

            {/* Right Column - Market Ticker & Tab Content (25% / 3 columns) */}
            <div className="col-span-12 lg:col-span-3 flex flex-col gap-4">
              {/* Market Ticker */}
              <div className="bg-[#111] rounded-3xl p-4 border border-[#1f1f22]">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white uppercase tracking-wide">
                    Market
                  </h3>
                  <span className="text-xs text-[#888]">{assets.length} assets</span>
                </div>
                <div className="max-h-[300px] overflow-y-auto custom-scrollbar">
                  <MarketTicker
                    assets={assets}
                    selectedAsset={selectedAsset}
                    onAssetSelect={handleAssetSelect}
                    isLoading={isLoadingAssets}
                  />
                </div>
              </div>

              {/* Tab Content Panel */}
              <div className="bg-[#111] rounded-3xl border border-[#1f1f22] overflow-hidden min-h-[400px]">
                <div className="h-full max-h-[600px] overflow-y-auto custom-scrollbar">
                  {renderTabContent()}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating AI Chat */}
      <FloatingChat
        messages={chatMessages}
        onSendMessage={handleSendMessage}
      />
    </div>
  );
};

export default Index;