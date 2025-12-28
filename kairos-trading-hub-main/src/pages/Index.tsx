import { useState, useEffect } from "react";
import { LeftSidebar } from "@/components/dashboard/LeftSidebar";
import { ChartPanel } from "@/components/dashboard/ChartPanel";
import { TerminalLog } from "@/components/dashboard/TerminalLog";
import { RightPanel } from "@/components/dashboard/RightPanel";
import { Asset, TradingMode, LogEntry, ChatMessage, MOCK_ASSETS } from "@/types/trading";
import { toast } from "@/hooks/use-toast";

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
        const response = await fetch('/api/watchlist');
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
      try {
        // Map Trading Mode to Interval
        let interval = "15m";
        if (tradingMode === 'scalping') interval = "1m";
        if (tradingMode === 'swing') interval = "4h";

        // console.log("Fetching candles for:", activeSymbol);
        const response = await fetch(`/api/candles?symbol=${activeSymbol}&interval=${interval}`);
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
      await fetch("/api/trade-settings", {
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
      const response = await fetch('/api/chat', {
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

      const response = await fetch(`/api/trade?action=${action}`, {
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
      
      const response = await fetch("/api/force-close", {
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
        const response = await fetch("/api/logs?limit=20");
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

  return (
    <div className="h-screen w-full flex bg-background overflow-hidden">
      {/* Left Sidebar - Navigation */}
      <LeftSidebar
        tradingMode={tradingMode}
        onModeChange={handleModeChange}
        assets={assets}
        selectedAsset={selectedAsset}
        onAssetSelect={handleAssetSelect}
        isLoading={isLoadingAssets}
      />

      {/* Center Panel - Charts & Logs */}
      <main className="flex-1 flex flex-col h-full min-w-0">
        {/* CRITICAL: Passing real 'chartData' to the component */}
        <ChartPanel
          asset={currentAsset}
          tradingMode={tradingMode}
          data={chartData}
        />
        <TerminalLog logs={logs} />
      </main>

      {/* Right Panel - AI Chat & Execution */}
      <RightPanel
        asset={currentAsset}
        messages={chatMessages}
        onSendMessage={handleSendMessage}
        onAuthorizeTrade={handleAuthorizeTrade}
        onForceClose={handleForceClose}
      />
    </div>
  );
};

export default Index;