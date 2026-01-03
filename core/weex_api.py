import requests
import time
import hmac
import hashlib
import base64
import json
import os
import random
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

class WeexClient:
    def __init__(self, api_key=None, secret_key=None, passphrase=None):
        # Support both constructor args and env vars
        self.api_key = api_key or os.getenv("WEEX_API_KEY")
        self.secret_key = secret_key or os.getenv("WEEX_SECRET")
        self.passphrase = passphrase or os.getenv("WEEX_PASSPHRASE")
        
        self.base_url = "https://api-contract.weex.com"

    def _generate_signature(self, method, path, query_string="", body=""):
        timestamp = str(int(time.time() * 1000))
        
        # Build pre-hash string according to WEEX API spec
        if method == "GET":
            if query_string:
                pre_hash = f"{timestamp}{method.upper()}{path}?{query_string}"
            else:
                pre_hash = f"{timestamp}{method.upper()}{path}"
        else:
            pre_hash = f"{timestamp}{method.upper()}{path}{body}"
        
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            pre_hash.encode('utf-8'),
            hashlib.sha256
        ).digest()
        
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        return signature_b64, timestamp

    def _send_weex_request(self, method, endpoint, params=None, use_access_headers=False):
        """
        Sends authenticated requests to WEEX (for ordering)
        use_access_headers: True for /capi/v2/* endpoints (ACCESS-* format), False for /api/contract/* (X-WEEX-* format)
        """
        if params is None:
            params = {}
            
        path = endpoint
        query_string = ""
        body_str = ""

        if method == "GET" and params:
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        elif method == "POST" and params:
            body_str = json.dumps(params)

        signature, timestamp = self._generate_signature(method, path, query_string, body_str)
        
        if use_access_headers:
            headers = {
                "Content-Type": "application/json",
                "ACCESS-KEY": self.api_key,
                "ACCESS-SIGN": signature,
                "ACCESS-PASSPHRASE": self.passphrase,
                "ACCESS-TIMESTAMP": timestamp,
                "locale": "zh-CN"
            }
        else:
            headers = {
                "Content-Type": "application/json",
                "X-WEEX-API-KEY": self.api_key,
                "X-WEEX-PASSPHRASE": self.passphrase,
                "X-WEEX-TIMESTAMP": timestamp,
                "X-WEEX-SIGNATURE": signature
            }
        
        url = f"{self.base_url}{path}"
        
        try:
            if method == "GET":
                res = requests.get(url, headers=headers, params=params if params else None, timeout=5)
            else:
                res = requests.post(url, headers=headers, json=params if params else {}, timeout=5)
            
            if res.status_code != 200:
                print(f"WEEX API Error {res.status_code}: {res.text[:200] if res.text else 'No response body'}")
                return None
            
            if not res.text or res.text.strip() == "":
                print(f"WEEX API Error: Empty response from server (status {res.status_code})")
                return None
            
            try:
                return res.json()
            except json.JSONDecodeError as e:
                print(f"WEEX API Error: Invalid JSON response - {res.text[:200]}")
                print(f"JSON Parse Error: {e}")
                return None
        except requests.exceptions.Timeout:
            print(f"WEEX API Error: Request timeout (5s)")
            return None
        except requests.exceptions.ConnectionError as e:
            print(f"WEEX API Error: Connection failed - {str(e)[:200]}")
            return None
        except Exception as e:
            print(f"WEEX API Error: {type(e).__name__} - {str(e)[:200]}")
            return None

    def fetch_candles(self, symbol="cmt_btcusdt", limit=100, interval="15m"):
        """
        HYBRID STRATEGY: 
        Fetches Chart Data from BINANCE (Reliable/Public)
        Maps WEEX symbol 'cmt_btcusdt' -> Binance 'BTCUSDT'
        """
        binance_symbol = symbol.upper().replace("CMT_", "").replace("USDT", "USDT")
        if binance_symbol.endswith("_SPBL"): binance_symbol = binance_symbol.replace("_SPBL", "")
        
        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": binance_symbol,
            "interval": interval,
            "limit": str(limit)
        }
        
        try:
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            if isinstance(data, list) and len(data) > 0:
                return data
                
        except Exception as e:
            print(f"Binance Fetch Error: {e}")

        print("Network Blocked. Using Simulation Data.")
        return self._generate_mock_candles(limit)

    def place_order(self, side="buy", size="10", symbol="cmt_dogeusdt"):
        """
        Executes Trade on WEEX (Authenticated)
        Uses the new Contract API format
        """
        endpoint = "/api/contract/Transaction_API/PlaceOrder"
        
        params = {
            "symbol": symbol,
            "side": 1 if side.lower() == "buy" else 2,  
            "type": 2,        
            "quantity": str(size),  
            "leverage": 10    
        }
        
        print(f"Sending Order to WEEX: {params}")
        
        res = self._send_weex_request("POST", endpoint, params)
        
        print(f"WEEX Response: {res}")
        
        if res:
            if isinstance(res, dict):
                if res.get("code") == "00000" or res.get("status") == "success":
                    print(f"WEEX ORDER SUCCESS: {res}")
                    return res
                else:
                    print(f"WEEX API Error: {res.get('msg', res.get('message', 'Unknown error'))}")
                    return res
            else:
                return res
        else:
            print(f"No response from WEEX API")
            return {"code": "ERROR", "msg": "No response from WEEX", "data": None}

    def execute_order(self, side, size="10", symbol="cmt_dogeusdt"):
        """Alias for place_order to support sentinel_service.py"""
        return self.place_order(side, size, symbol)
    
    def close_position(self, symbol, side, size=None):
        """
        Closes an existing position.
        side: 'buy' to close short, 'sell' to close long
        """
        endpoint = "/capi/v2/order/placeOrder"
        type_code = "4" if side.lower() == "buy" else "3"
        
        payload = {
            "symbol": symbol,
            "side": side.lower(),
            "orderType": "market",
            "size": str(size) if size else "10",
            "type": type_code,
            "match_price": "1"
        }
        
        print(f"Closing Position on WEEX: {payload}")
        res = self._send_weex_request("POST", endpoint, payload)
        print(f"WEEX Close Position Response: {res}")
        return res
    
    def get_balance(self):
        """
        Fetches account assets/balance using /capi/v2/account/assets endpoint
        Automatically uses ACCESS-* header format
        """
        endpoint = "/capi/v2/account/assets"
        return self._send_weex_request("GET", endpoint)
    
    def set_leverage(self, symbol="cmt_btcusdt", leverage=10):
        """
        REQUIRED: Sets leverage before you can trade
        """
        params = {
            "symbol": symbol,
            "leverage": leverage,
            "side": 1  
        }
        endpoint = "/api/contract/Account_API/AdjustLeverage"
        return self._send_weex_request("POST", endpoint, params)
    
    def get_positions(self):
        """Fetches all open positions from WEEX. Automatically uses ACCESS-* headers for /capi/v2/* endpoints."""
        endpoint = "/capi/v2/position/list"
        res = self._send_weex_request("GET", endpoint)
        return res
    
    def close_all_positions(self):
        """Closes all open positions."""
        try:
            positions = self.get_positions()
            results = []
            
            if positions and positions.get("code") == "00000" and positions.get("data"):
                for pos in positions.get("data", []):
                    symbol = pos.get("symbol")
                    side = pos.get("side")  
                    size = pos.get("size")
                    
                    if symbol and side and size:
                        # Close position: opposite side
                        close_side = "sell" if side == "long" else "buy"
                        result = self.close_position(symbol, close_side, size)
                        results.append({
                            "symbol": symbol,
                            "side": side,
                            "result": result
                        })
                
                return {"status": "success", "closed": len(results), "results": results}
            else:
                return {"status": "success", "message": "No open positions to close", "closed": 0}
        except Exception as e:
            return {"status": "error", "msg": str(e)}

    def _generate_mock_candles(self, limit):
        """Generates realistic fake data so the chart is never empty"""
        candles = []
        price = 98000.00 
        now = int(time.time() * 1000)
        for i in range(limit):
            timestamp = now - ((limit - i) * 15 * 60 * 1000)
            change = random.uniform(-50, 60)
            open_p = price
            close_p = price + change
            high_p = max(open_p, close_p) + random.uniform(0, 20)
            low_p = min(open_p, close_p) - random.uniform(0, 20)
            candles.append([timestamp, str(open_p), str(high_p), str(low_p), str(close_p), "1000"])
            price = close_p 
        return candles