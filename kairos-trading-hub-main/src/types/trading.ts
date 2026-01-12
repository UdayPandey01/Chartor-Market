export type TradingMode = 'scalping' | 'intraday' | 'swing' | 'institutional';

export interface Asset {
  symbol: string;
  pair: string;
  price: number;
  change24h: number;
  volume24h: number;
  high24h: number;
  low24h: number;
  raw_symbol?: string; // WEEX API symbol format (e.g., "cmt_btcusdt")
}

export interface LogEntry {
  id: string;
  timestamp: Date;
  type: 'sentinel' | 'risk' | 'trade' | 'system';
  message: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export const TRADING_MODES: Record<TradingMode, { label: string; timeframes: string; color: string }> = {
  scalping: { label: 'Scalping', timeframes: '1m/5m', color: 'scalping' },
  intraday: { label: 'Intraday', timeframes: '15m/1h', color: 'intraday' },
  swing: { label: 'Swing', timeframes: '4h/1D', color: 'swing' },
  institutional: { label: 'Institutional', timeframes: 'Multi-TF', color: 'institutional' },
};

export const MOCK_ASSETS: Asset[] = [
  { symbol: 'BTC', pair: 'BTC/USDT', price: 98420.50, change24h: 2.34, volume24h: 2890000000, high24h: 99100, low24h: 96800 },
  { symbol: 'ETH', pair: 'ETH/USDT', price: 3842.15, change24h: -0.87, volume24h: 1420000000, high24h: 3900, low24h: 3780 },
  { symbol: 'SOL', pair: 'SOL/USDT', price: 198.42, change24h: 5.21, volume24h: 890000000, high24h: 205, low24h: 188 },
  { symbol: 'BNB', pair: 'BNB/USDT', price: 712.80, change24h: 1.12, volume24h: 456000000, high24h: 720, low24h: 698 },
  { symbol: 'XRP', pair: 'XRP/USDT', price: 2.34, change24h: -2.15, volume24h: 234000000, high24h: 2.45, low24h: 2.28 },
  { symbol: 'ADA', pair: 'ADA/USDT', price: 1.12, change24h: 3.45, volume24h: 178000000, high24h: 1.15, low24h: 1.05 },
  { symbol: 'DOGE', pair: 'DOGE/USDT', price: 0.412, change24h: -1.23, volume24h: 567000000, high24h: 0.425, low24h: 0.398 },
  { symbol: 'LTC', pair: 'LTC/USDT', price: 108.90, change24h: 0.78, volume24h: 89000000, high24h: 112, low24h: 106 },
];
