"""
Kalshi Trade Executor

Real trade execution via Kalshi's private trading API (v2).
Uses RSA-PSS signature authentication as required by Kalshi API v2.
Implements the TradeExecutor abstract interface from live.py.
"""

import os
import time
import base64
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False

from abc import ABC, abstractmethod

class TradeExecutor(ABC):
    """
    Abstract base class for trade execution.
    """
    
    @abstractmethod
    def connect(self, api_key: str, api_secret: str = None) -> bool:
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        pass
    
    @abstractmethod
    def get_balance(self) -> float:
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        pass
    
    @abstractmethod
    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: float,
        order_type: str = 'limit'
    ) -> Optional[str]:
        pass

    @abstractmethod
    def sell_position(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: float
    ) -> Optional[str]:
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass
        
    @abstractmethod
    def get_open_orders(self) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def get_fills(self, ticker: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        pass

class DryRunExecutor(TradeExecutor):
    """
    Dry-run executor that logs trades without executing them.
    Useful for testing and paper trading.
    """
    
    def __init__(self):
        self._connected = False
        self._balance = 1000.0  # Simulated bankroll
        self._positions = []
        self._orders = []
    
    def connect(self, api_key: str, api_secret: str = None) -> bool:
        print("📋 [DRY RUN] Connected to dry-run executor")
        self._connected = True
        return True
    
    def is_connected(self) -> bool:
        return self._connected
    
    def get_balance(self) -> float:
        return self._balance
    
    def get_positions(self) -> List[Dict[str, Any]]:
        return self._positions
    
    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: float,
        order_type: str = 'limit'
    ) -> Optional[str]:
        order_id = f"DRY-{len(self._orders)+1:04d}"
        self._orders.append({
            'order_id': order_id,
            'ticker': ticker,
            'side': side,
            'quantity': quantity,
            'limit_price': limit_price,
            'order_type': order_type,
            'timestamp': datetime.now()
        })
        print(f"📋 [DRY RUN] Order placed: {order_id}")
        print(f"    Ticker: {ticker}")
        print(f"    Side: {side.upper()}")
        print(f"    Quantity: {quantity}")
        print(f"    Price: ${limit_price:.2f}")
        
        # Simulate immediate fill for testing exit logic
        self._positions.append({
            'ticker': ticker,
            'quantity': quantity,
            'avg_price': limit_price,
            'side': side,
            'market_value': quantity * limit_price,
            'resting_orders': 0  # Initially 0, should trigger exit logic
        })
        print(f"    [DRY RUN] Simulating fill for {quantity} contracts")
        
        return order_id

    def sell_position(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: float
    ) -> Optional[str]:
        order_id = f"DRY-SELL-{len(self._orders)+1:04d}"
        print(f"📋 [DRY RUN] Sell Order placed: {order_id} for {quantity} {side} at ${limit_price:.2f}")
        
        # Remove from mock positions
        self._positions = [p for p in self._positions if not (p['ticker'] == ticker and p['side'] == side)]
        print(f"    [DRY RUN] Simulating exit fill for {ticker}")
            
        return order_id
    
    def cancel_order(self, order_id: str) -> bool:
        print(f"📋 [DRY RUN] Order cancelled: {order_id}")
        return True
        
    def get_open_orders(self) -> List[Dict[str, Any]]:
        return self._orders
        
    def get_fills(self, ticker: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        fills = []
        for order in self._orders[-limit:]:
            if 'filled' not in order and (ticker is None or order['ticker'] == ticker):
                order['filled'] = True
                fills.append({
                    'trade_id': f"FILL-{order['order_id']}",
                    'order_id': order['order_id'],
                    'ticker': order['ticker'],
                    'side': order['side'],
                    'count': order['quantity'],
                    'yes_price': int(order['limit_price'] * 100) if order['side'] == 'yes' else 0,
                    'no_price': int(order['limit_price'] * 100) if order['side'] == 'no' else 0,
                    'created_time': datetime.now().isoformat()
                })
        return fills


class KalshiExecutor(TradeExecutor):
    """
    Real Kalshi API trade executor.
    
    Uses RSA-PSS signature authentication for Kalshi API v2.
    Handles order placement via Kalshi's trading API.
    """
    
    # API endpoints (updated Feb 2026 - moved to api.elections.kalshi.com)
    PROD_URL = "https://api.elections.kalshi.com/trade-api/v2"
    DEMO_URL = "https://demo-api.kalshi.com/trade-api/v2"
    
    def __init__(self, use_demo: bool = False):
        """
        Initialize executor.
        
        Args:
            use_demo: If True, use demo API (no real money)
        """
        self.base_url = self.DEMO_URL if use_demo else self.PROD_URL
        self.use_demo = use_demo
        self.api_key_id: Optional[str] = None
        self.private_key = None
        self.member_id: Optional[str] = None
        self._connected = False
        self._balance: float = 0.0
    
    def connect(self, api_key_id: str, private_key_pem: str = None) -> bool:
        """
        Connect to Kalshi API using RSA key authentication.
        
        Args:
            api_key_id: Your Kalshi API Key ID (UUID)
            private_key_pem: RSA private key in PEM format (or path to .pem file)
        
        Returns:
            True if connection successful
        """
        if not HAS_CRYPTO:
            print("❌ cryptography library not installed")
            print("   Run: pip install cryptography")
            return False
        
        if not api_key_id:
            print("❌ Missing Kalshi API Key ID")
            return False
        
        self.api_key_id = api_key_id
        
        # Load private key
        if private_key_pem:
            try:
                self.private_key = self._load_private_key(private_key_pem)
            except Exception as e:
                print(f"❌ Failed to load private key: {e}")
                return False
        else:
            print("❌ Missing RSA private key")
            print("   Set KALSHI_PRIVATE_KEY or KALSHI_PRIVATE_KEY_FILE")
            return False
        
        # Test connection by getting balance
        try:
            self._connected = True  # Temporarily set for _update_balance
            self._update_balance()
            
            mode = "DEMO" if self.use_demo else "LIVE"
            print(f"✅ Connected to Kalshi [{mode}] via RSA authentication")
            print(f"   API Key ID: {api_key_id[:8]}...{api_key_id[-4:]}")
            print(f"   Balance: ${self._balance:.2f}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            self._connected = False
            return False
    
    def _load_private_key(self, key_or_path: str):
        """Load RSA private key from PEM string or file path."""
        # Check if it's a file path
        if os.path.exists(key_or_path):
            with open(key_or_path, 'rb') as f:
                key_data = f.read()
        else:
            # Assume it's the key itself - handle escaped newlines
            key_str = key_or_path.replace('\\n', '\n')
            key_data = key_str.encode('utf-8')
        
        return serialization.load_pem_private_key(
            key_data,
            password=None,
            backend=default_backend()
        )
    
    def _sign_request(self, method: str, path: str) -> Dict[str, str]:
        """
        Generate authentication headers with RSA-PSS signature.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            path: Request path (without query params)
        
        Returns:
            Dict with required authentication headers
        """
        timestamp = str(int(time.time() * 1000))  # Milliseconds
        
        # Message to sign: timestamp + method + path
        message = f"{timestamp}{method}{path}"
        
        # Sign with RSA-PSS
        signature = self.private_key.sign(
            message.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Base64 encode the signature
        signature_b64 = base64.b64encode(signature).decode('utf-8')
        
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature_b64,
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, path: str, params: Dict = None, json_data: Dict = None):
        """Make an authenticated request to the Kalshi API."""
        url = f"{self.base_url}{path}"
        headers = self._sign_request(method, f"/trade-api/v2{path}")
        
        if method == "GET":
            resp = requests.get(url, headers=headers, params=params)
        elif method == "POST":
            resp = requests.post(url, headers=headers, json=json_data)
        elif method == "DELETE":
            resp = requests.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        resp.raise_for_status()
        return resp.json()
    
    def _update_balance(self):
        """Fetch current balance from API."""
        if not self._connected:
            return
        
        try:
            data = self._make_request("GET", "/portfolio/balance")
            # Balance is in cents
            self._balance = data.get("balance", 0) / 100
        except Exception as e:
            print(f"   ⚠ Balance fetch failed: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to trading API."""
        return self._connected
    
    def get_balance(self) -> float:
        """Get current account balance in dollars."""
        self._update_balance()
        return self._balance
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get current open positions.
        
        Returns:
            List of position dicts with keys: ticker, quantity, avg_price, side
        """
        if not self._connected:
            return []
        
        try:
            data = self._make_request("GET", "/portfolio/positions", 
                                      params={"limit": 100, "settlement_status": "unsettled"})
            
            positions = []
            for mp in data.get("market_positions", []):
                yes_qty = mp.get("position", 0)
                
                if yes_qty != 0:
                    positions.append({
                        'ticker': mp.get("ticker", ""),
                        'quantity': abs(yes_qty),
                        'avg_price': mp.get("average_price", 0) / 100,
                        'side': 'yes' if yes_qty > 0 else 'no',
                        'market_value': mp.get("market_exposure", 0) / 100,
                        'resting_orders': mp.get("resting_orders_count", 0)
                    })
            
            return positions
            
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []
    
    def place_order(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: float,
        order_type: str = 'limit'
    ) -> Optional[str]:
        """
        Place a trade order.
        
        Args:
            ticker: Market ticker (e.g., KXNBAGAME-24DEC16LALNY-LAL)
            side: 'yes' or 'no'
            quantity: Number of contracts
            limit_price: Limit price in dollars (0.01-0.99)
            order_type: 'limit' or 'market'
            
        Returns:
            Order ID if successful, None otherwise
        """
        if not self._connected:
            print("❌ Not connected")
            return None
        
        if quantity <= 0:
            print("❌ Invalid quantity")
            return None
        
        price_cents = int(limit_price * 100)
        
        if price_cents < 1 or price_cents > 99:
            print(f"❌ Invalid price: ${limit_price:.2f}")
            return None
        
        payload = {
            "ticker": ticker,
            "action": "buy",
            "side": side,
            "count": quantity,
            "type": order_type,
        }
        
        if order_type == 'limit':
            payload["yes_price"] = price_cents if side == "yes" else None
            payload["no_price"] = price_cents if side == "no" else None
        
        try:
            data = self._make_request("POST", "/portfolio/orders", json_data=payload)
            
            order = data.get("order", {})
            order_id = order.get("order_id")
            
            if order_id:
                status = order.get("status", "unknown")
                filled = order.get("filled_count", 0)
                print(f"✅ Order placed: {order_id}")
                print(f"   Ticker: {ticker}")
                print(f"   Side: {side.upper()}")
                print(f"   Quantity: {quantity}")
                print(f"   Price: ${limit_price:.2f}")
                print(f"   Status: {status} (filled: {filled})")
                return order_id
            else:
                print("❌ No order ID in response")
                return None
                
        except requests.exceptions.HTTPError as e:
            print(f"❌ Order failed: {e}")
            return None
        except Exception as e:
            print(f"❌ Order error: {e}")
            return None
    
    def sell_position(
        self,
        ticker: str,
        side: str,
        quantity: int,
        limit_price: float
    ) -> Optional[str]:
        """Sell/close a position."""
        if not self._connected:
            return None
        
        price_cents = int(limit_price * 100)
        
        payload = {
            "ticker": ticker,
            "action": "sell",
            "side": side,
            "count": quantity,
            "type": "limit",
        }
        
        if side == "yes":
            payload["yes_price"] = price_cents
        else:
            payload["no_price"] = price_cents
        
        try:
            data = self._make_request("POST", "/portfolio/orders", json_data=payload)
            
            order = data.get("order", {})
            order_id = order.get("order_id")
            
            if order_id:
                print(f"✅ Sell order placed: {order_id}")
                return order_id
            return None
            
        except Exception as e:
            print(f"❌ Sell order failed: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if not self._connected:
            return False
        
        try:
            self._make_request("DELETE", f"/portfolio/orders/{order_id}")
            print(f"✅ Order cancelled: {order_id}")
            return True
        except Exception as e:
            print(f"❌ Cancel failed: {e}")
            return False
    
    def get_open_orders(self) -> List[Dict[str, Any]]:
        """Get all open/resting orders."""
        if not self._connected:
            return []
        
        try:
            data = self._make_request("GET", "/portfolio/orders", params={"status": "resting"})
            return data.get("orders", [])
        except:
            return []
    
    def get_fills(self, ticker: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent order fills."""
        if not self._connected:
            return []
        
        params = {"limit": limit}
        if ticker:
            params["ticker"] = ticker
        
        try:
            data = self._make_request("GET", "/portfolio/fills", params=params)
            return data.get("fills", [])
        except:
            return []
