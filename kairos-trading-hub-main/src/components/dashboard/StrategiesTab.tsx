import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Switch } from "@/components/ui/switch";
import { Target, Play, Pause, RefreshCw, AlertCircle, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface Strategy {
  id: number;
  name: string;
  description: string | null;
  logic: string;
  action: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export function StrategiesTab() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    prompt: "",
    description: ""
  });

  useEffect(() => {
    fetchStrategies();
    const interval = setInterval(fetchStrategies, 10000); 
    return () => clearInterval(interval);
  }, []);

  const fetchStrategies = async () => {
    try {
      const response = await fetch("/api/strategies");
      const data = await response.json();
      
      if (data.status === "success" && data.strategies) {
        setStrategies(data.strategies);
      }
      setIsLoading(false);
    } catch (error) {
      console.error("Failed to fetch strategies:", error);
      setIsLoading(false);
    }
  };

  const toggleStrategy = async (strategyId: number, currentStatus: boolean) => {
    setTogglingId(strategyId);
    try {
      const response = await fetch(`/api/strategies/${strategyId}/toggle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !currentStatus })
      });
      
      const result = await response.json();
      if (result.status === "success") {
        setStrategies(prev => prev.map(s => 
          s.id === strategyId 
            ? { ...s, is_active: !currentStatus }
            : s
        ));
        fetchStrategies();
      }
    } catch (error) {
      console.error("Failed to toggle strategy:", error);
    } finally {
      setTogglingId(null);
    }
  };

  const handleCreateStrategy = async () => {
    if (!formData.name.trim() || !formData.prompt.trim()) {
      return;
    }

    setCreating(true);
    try {
      const response = await fetch("/api/create-strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name,
          prompt: formData.prompt,
          description: formData.description || null
        })
      });

      const result = await response.json();
      if (result.status === "success") {
        setFormData({ name: "", prompt: "", description: "" });
        setShowCreateForm(false);
        fetchStrategies();
      } else {
        alert(`Failed to create strategy: ${result.msg}`);
      }
    } catch (error) {
      console.error("Failed to create strategy:", error);
      alert("Failed to create strategy. Please try again.");
    } finally {
      setCreating(false);
    }
  };

  const getActionColor = (action: string) => {
    return action === "BUY" ? "text-success" : action === "SELL" ? "text-destructive" : "text-muted-foreground";
  };

  const getActionBg = (action: string) => {
    return action === "BUY" ? "bg-success/10 border-success/20" : action === "SELL" ? "bg-destructive/10 border-destructive/20" : "bg-muted/10 border-muted/20";
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-primary" />
            <span className="text-sm font-medium text-foreground">Strategy Marketplace</span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchStrategies}
              className="h-6 w-6 p-0"
              disabled={isLoading}
            >
              <RefreshCw className={cn("w-3 h-3", isLoading && "animate-spin")} />
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => setShowCreateForm(true)}
              className="h-7 px-2 text-xs"
            >
              <Plus className="w-3 h-3 mr-1" />
              Create
            </Button>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">Enable strategies to auto-trade based on market conditions</p>
      </div>

      {/* Create Strategy Modal */}
      {showCreateForm && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-border rounded-lg shadow-lg w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-foreground">Create New Strategy</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setShowCreateForm(false);
                  setFormData({ name: "", prompt: "", description: "" });
                }}
                className="h-6 w-6 p-0"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-xs text-muted-foreground uppercase mb-1 block">
                  Strategy Name
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., RSI Oversold Buy"
                  className="w-full"
                />
              </div>

              <div>
                <label className="text-xs text-muted-foreground uppercase mb-1 block">
                  Strategy Logic (Plain English)
                </label>
                <Textarea
                  value={formData.prompt}
                  onChange={(e) => setFormData({ ...formData, prompt: e.target.value })}
                  placeholder="e.g., Buy when RSI is under 30 and price is above EMA 20"
                  className="w-full min-h-[100px] resize-none"
                />
                <p className="text-[10px] text-muted-foreground mt-1">
                  Describe your trading strategy in plain English. Gemini will convert it to logic.
                </p>
              </div>

              <div>
                <label className="text-xs text-muted-foreground uppercase mb-1 block">
                  Description (Optional)
                </label>
                <Input
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Brief description of the strategy"
                  className="w-full"
                />
              </div>

              <div className="flex gap-2 pt-2">
                <Button
                  onClick={handleCreateStrategy}
                  disabled={creating || !formData.name.trim() || !formData.prompt.trim()}
                  className="flex-1"
                >
                  {creating ? (
                    <>
                      <RefreshCw className="w-3 h-3 mr-2 animate-spin" />
                      Generating...
                    </>
                  ) : (
                    <>
                      <Plus className="w-3 h-3 mr-2" />
                      Generate & Save
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    setShowCreateForm(false);
                    setFormData({ name: "", prompt: "", description: "" });
                  }}
                >
                  Cancel
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Active Count */}
      <div className="p-4 border-b border-border bg-card/50">
        <div className="flex items-center justify-between">
          <div className="text-xs text-muted-foreground uppercase">Active Strategies</div>
          <div className="text-lg font-mono font-bold text-primary">
            {strategies.filter(s => s.is_active).length} / {strategies.length}
          </div>
        </div>
      </div>

      {/* Strategies List */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <div className="w-16 h-16 rounded-2xl bg-muted/50 flex items-center justify-center mb-4 animate-pulse">
              <Target className="w-8 h-8 text-muted-foreground/50" />
            </div>
            <div className="text-sm font-medium text-muted-foreground mb-1">
              Loading Strategies...
            </div>
          </div>
        ) : strategies.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Target className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
            <div className="text-sm font-medium text-muted-foreground mb-1">
              No Strategies Available
            </div>
            <div className="text-xs text-muted-foreground/60">
              Strategies will appear here when added
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {strategies.map((strategy) => (
              <div
                key={strategy.id}
                className={cn(
                  "rounded-lg p-4 border transition-all",
                  strategy.is_active 
                    ? "bg-card border-primary/20 shadow-sm" 
                    : "bg-muted/30 border-border/50"
                )}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      {strategy.is_active ? (
                        <Play className="w-4 h-4 text-success" />
                      ) : (
                        <Pause className="w-4 h-4 text-muted-foreground" />
                      )}
                      <h3 className="text-sm font-bold text-foreground">
                        {strategy.name}
                      </h3>
                      <span className={cn(
                        "text-xs px-2 py-0.5 rounded-full font-medium",
                        getActionBg(strategy.action),
                        getActionColor(strategy.action)
                      )}>
                        {strategy.action}
                      </span>
                    </div>
                    {strategy.description && (
                      <p className="text-xs text-muted-foreground mb-2">
                        {strategy.description}
                      </p>
                    )}
                    <div className="bg-background/50 rounded p-2 mt-2">
                      <div className="text-[10px] text-muted-foreground uppercase mb-1">Logic</div>
                      <code className="text-xs font-mono text-foreground">
                        {strategy.logic}
                      </code>
                    </div>
                  </div>
                  <div className="ml-4 flex items-center">
                    <Switch
                      checked={strategy.is_active}
                      onCheckedChange={() => toggleStrategy(strategy.id, strategy.is_active)}
                      disabled={togglingId === strategy.id}
                    />
                  </div>
                </div>
                
                {strategy.is_active && (
                  <div className="mt-3 pt-3 border-t border-border/50">
                    <div className="flex items-center gap-1.5 text-xs text-success">
                      <AlertCircle className="w-3 h-3" />
                      <span>Active - Will auto-trade when conditions are met</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

