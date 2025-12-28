import { LogEntry } from "@/types/trading";
import { cn } from "@/lib/utils";
import { useEffect, useRef } from "react";

interface TerminalLogProps {
  logs: LogEntry[];
}

export function TerminalLog({ logs }: TerminalLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const getTypeColor = (type: LogEntry['type']) => {
    switch (type) {
      case 'sentinel': return 'text-primary';
      case 'risk': return 'text-warning';
      case 'trade': return 'text-success';
      case 'system': return 'text-muted-foreground';
      default: return 'text-foreground';
    }
  };

  const getTypeLabel = (type: LogEntry['type']) => {
    return `[${type.toUpperCase()}]`;
  };

  return (
    <div className="h-40 bg-background border-t border-border overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card/50">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          System Terminal
        </span>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-destructive/50" />
          <div className="w-2 h-2 rounded-full bg-warning/50" />
          <div className="w-2 h-2 rounded-full bg-success/50" />
        </div>
      </div>
      <div 
        ref={scrollRef}
        className="h-[calc(100%-36px)] overflow-y-auto scrollbar-thin p-3 font-mono text-xs space-y-1"
      >
        {logs.map((log) => (
          <div key={log.id} className="flex gap-2 animate-slide-up">
            <span className="text-muted-foreground/60">{formatTime(log.timestamp)}</span>
            <span className={cn("font-semibold min-w-[80px]", getTypeColor(log.type))}>
              {getTypeLabel(log.type)}
            </span>
            <span className="text-muted-foreground">{log.message}</span>
          </div>
        ))}
        <div className="flex items-center gap-1 text-muted-foreground/40">
          <span className="animate-pulse">▌</span>
        </div>
      </div>
    </div>
  );
}
