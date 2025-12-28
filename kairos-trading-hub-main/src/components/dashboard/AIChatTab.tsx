import { useState } from "react";
import React from "react";
import { ChatMessage } from "@/types/trading";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { Send, Bot, User, Sparkles } from "lucide-react";

interface AIChatTabProps {
  messages: ChatMessage[];
  onSendMessage: (message: string) => void;
}

export function AIChatTab({ messages, onSendMessage }: AIChatTabProps) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      onSendMessage(input.trim());
      setInput("");
    }
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
  };

  const formatMessageWithHighlights = (text: string): React.ReactNode => {
    // Simple regex-based highlighting for prices, percentages, and bold text
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let keyCounter = 0;
    
    // Pattern for prices: $87,687.73 or $87,687
    const pricePattern = /\$[\d,]+(?:\.\d{1,2})?/g;
    // Pattern for percentages: 67.2% or 67%
    const percentPattern = /\d+\.?\d*%/g;
    // Pattern for bold text: **text**
    const boldPattern = /\*\*([^*]+)\*\*/g;
    
    // Collect all matches with their positions
    const matches: Array<{index: number; end: number; type: 'price' | 'percent' | 'bold'; value: string}> = [];
    
    let match;
    while ((match = pricePattern.exec(text)) !== null) {
      matches.push({
        index: match.index,
        end: match.index + match[0].length,
        type: 'price',
        value: match[0]
      });
    }
    
    while ((match = percentPattern.exec(text)) !== null) {
      matches.push({
        index: match.index,
        end: match.index + match[0].length,
        type: 'percent',
        value: match[0]
      });
    }
    
    while ((match = boldPattern.exec(text)) !== null) {
      matches.push({
        index: match.index,
        end: match.index + match[0].length,
        type: 'bold',
        value: match[1] // Just the text inside **
      });
    }
    
    // Sort by index
    matches.sort((a, b) => a.index - b.index);
    
    // Remove overlaps (keep first match)
    const filteredMatches = [];
    for (const m of matches) {
      const overlaps = filteredMatches.some(fm => 
        (m.index >= fm.index && m.index < fm.end) ||
        (fm.index >= m.index && fm.index < m.end)
      );
      if (!overlaps) {
        filteredMatches.push(m);
      }
    }
    
    // Build JSX
    filteredMatches.forEach((match) => {
      // Add text before match
      if (match.index > lastIndex) {
        const beforeText = text.substring(lastIndex, match.index);
        if (beforeText) {
          parts.push(<React.Fragment key={`text-${keyCounter++}`}>{beforeText}</React.Fragment>);
        }
      }
      
      // Add highlighted match
      if (match.type === 'bold') {
        parts.push(
          <strong key={`bold-${keyCounter++}`} className="font-bold text-foreground">
            {match.value}
          </strong>
        );
      } else if (match.type === 'price') {
        parts.push(
          <span key={`price-${keyCounter++}`} className="text-success font-mono font-semibold">
            {match.value}
          </span>
        );
      } else if (match.type === 'percent') {
        parts.push(
          <span key={`percent-${keyCounter++}`} className="text-warning font-mono font-semibold">
            {match.value}
          </span>
        );
      }
      
      lastIndex = match.end;
    });
    
    // Add remaining text
    if (lastIndex < text.length) {
      const remainingText = text.substring(lastIndex);
      if (remainingText) {
        parts.push(<React.Fragment key={`text-${keyCounter++}`}>{remainingText}</React.Fragment>);
      }
    }
    
    return parts.length > 0 ? <>{parts}</> : text;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="flex items-center gap-3 p-4 border-b border-border">
        <div className="relative">
          <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
            <Bot className="w-4 h-4 text-primary" />
          </div>
          <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-success border-2 border-card" />
        </div>
        <div>
          <div className="text-sm font-medium text-foreground">Chartor AI</div>
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <Sparkles className="w-3 h-3" /> Market Intelligence
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="relative mx-auto w-16 h-16 mb-4">
              <div className="absolute inset-0 rounded-full bg-primary/20 animate-pulse" />
              <div className="relative w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="w-8 h-8 text-primary" />
              </div>
            </div>
            <p className="text-sm font-medium text-foreground mb-1">Welcome to Chartor AI</p>
            <p className="text-xs text-muted-foreground mb-4">
              Ask about market analysis, patterns, or trading strategies
            </p>
            <div className="flex flex-wrap gap-2 justify-center max-w-xs mx-auto">
              {["Analyze BTC trend", "What's the RSI?", "Market sentiment?"].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => onSendMessage(suggestion)}
                  className="text-xs px-3 py-1.5 rounded-full bg-muted hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex gap-3 animate-slide-up",
              msg.role === 'user' ? "justify-end" : "justify-start"
            )}
          >
            {msg.role === 'assistant' && (
              <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0 shadow-sm">
                <Bot className="w-4 h-4 text-primary" />
              </div>
            )}
            <div className={cn(
              "max-w-[85%] rounded-xl px-4 py-2.5 shadow-sm",
              msg.role === 'user' 
                ? "bg-primary text-primary-foreground rounded-br-sm" 
                : "bg-muted/80 text-foreground rounded-bl-sm border border-border/50"
            )}>
              {msg.role === 'assistant' ? (
                <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                  {formatMessageWithHighlights(msg.content)}
                </div>
              ) : (
                <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
              )}
              <p className={cn(
                "text-[10px] mt-1.5 opacity-70",
                msg.role === 'user' ? "text-primary-foreground/70" : "text-muted-foreground"
              )}>
                {formatTime(msg.timestamp)}
              </p>
            </div>
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-lg bg-secondary flex items-center justify-center flex-shrink-0 shadow-sm">
                <User className="w-4 h-4 text-muted-foreground" />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-border bg-card/50">
        <div className="flex gap-2 items-end">
          <div className="flex-1 relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Chartor about the market..."
              className="w-full bg-background border border-border rounded-lg px-4 py-2.5 pr-10 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50 transition-all"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
            {input.trim() && (
              <div className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-muted-foreground/50">
                Enter to send
              </div>
            )}
          </div>
          <Button 
            type="submit" 
            size="icon" 
            disabled={!input.trim()}
            className="h-10 w-10 shrink-0"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </form>
    </div>
  );
}
