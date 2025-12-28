import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AIChatTab } from "./AIChatTab";
import { SentinelControlTab } from "./SentinelControlTab";
import { TradesHistoryTab } from "./TradesHistoryTab";
import { PositionsTab } from "./PositionsTab";
import { RiskMetricsTab } from "./RiskMetricsTab";
import { StrategiesTab } from "./StrategiesTab";
import { Asset, ChatMessage } from "@/types/trading";
import { MessageSquare, Shield, Activity, DollarSign, BarChart3, Target } from "lucide-react";

interface RightPanelProps {
  asset: Asset;
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
  onAuthorizeTrade: (type: 'long' | 'short') => void;
  onForceClose: () => void;
}

export function RightPanel({ asset, messages, onSendMessage, onAuthorizeTrade, onForceClose }: RightPanelProps) {
  return (
    <aside className="w-80 h-full flex flex-col bg-card border-l border-border">
      <Tabs defaultValue="chat" className="flex flex-col h-full">
        <TabsList className="w-full rounded-none border-b border-border bg-transparent p-0 h-auto grid grid-cols-6">
          <TabsTrigger 
            value="chat" 
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 gap-1.5 text-xs"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Chat</span>
          </TabsTrigger>
          <TabsTrigger 
            value="sentinel" 
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 gap-1.5 text-xs"
          >
            <Shield className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sentinel</span>
          </TabsTrigger>
          <TabsTrigger 
            value="strategies" 
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 gap-1.5 text-xs"
          >
            <Target className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Strategies</span>
          </TabsTrigger>
          <TabsTrigger 
            value="trades" 
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 gap-1.5 text-xs"
          >
            <Activity className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Trades</span>
          </TabsTrigger>
          <TabsTrigger 
            value="positions" 
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 gap-1.5 text-xs"
          >
            <DollarSign className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Positions</span>
          </TabsTrigger>
          <TabsTrigger 
            value="metrics" 
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent py-2.5 gap-1.5 text-xs"
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Metrics</span>
          </TabsTrigger>
        </TabsList>
        
        <TabsContent value="chat" className="flex-1 mt-0 overflow-hidden">
          <AIChatTab messages={messages} onSendMessage={onSendMessage} />
        </TabsContent>
        
        <TabsContent value="sentinel" className="flex-1 mt-0 overflow-hidden">
          <SentinelControlTab 
            asset={asset} 
            onAuthorizeTrade={onAuthorizeTrade}
            onForceClose={onForceClose}
          />
        </TabsContent>
        
        <TabsContent value="strategies" className="flex-1 mt-0 overflow-hidden">
          <StrategiesTab />
        </TabsContent>
        
        <TabsContent value="trades" className="flex-1 mt-0 overflow-hidden">
          <TradesHistoryTab />
        </TabsContent>
        
        <TabsContent value="positions" className="flex-1 mt-0 overflow-hidden">
          <PositionsTab />
        </TabsContent>
        
        <TabsContent value="metrics" className="flex-1 mt-0 overflow-hidden">
          <RiskMetricsTab />
        </TabsContent>
      </Tabs>
    </aside>
  );
}
