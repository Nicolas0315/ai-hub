"""
bitflyer_client.py — BitFlyer REST API Client

Covers:
  Public : ticker, executions, board (BTC_JPY + FX_BTC_JPY)
  Private: getbalance, sendchildorder, cancelchildorder,
           getchildorders, getpositions
  Auth   : HMAC-SHA256 (env vars BITFLYER_API_KEY / BITFLYER_API_SECRET)
  Rate   : 500 req / 5 min token-bucket
  WS     : realtime ticker via websockets (falls back to polling)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────
BASE_URL = "https://api.bitflyer.com/v1"
PRODUCTS = ["BTC_JPY", "FX_BTC_JPY"]

# Rate limiter: 500 req / 300 s = 1.667 req/s
RATE_LIMIT_REQUESTS = 500
RATE_LIMIT_WINDOW_S = 300


# ── Rate Limiter ───────────────────────────────────────────────

class RateLimiter:
    """Thread-safe token-bucket rate limiter."""

    def __init__(self, max_calls: int = RATE_LIMIT_REQUESTS,
                 period: float = RATE_LIMIT_WINDOW_S) -> None:
        self.max_calls = max_calls
        self.period = period
        self._lock = threading.Lock()
        self._timestamps: list[float] = []

    def wait(self) -> None:
        """Block until a request slot is available."""
        with self._lock:
            now = time.monotonic()
            # Purge timestamps outside the window
            cutoff = now - self.period
            self._timestamps = [t for t in self._timestamps if t > cutoff]
            if len(self._timestamps) >= self.max_calls:
                sleep_for = self._timestamps[0] - cutoff
                logger.debug("Rate limit: sleeping %.2fs", sleep_for)
                time.sleep(sleep_for)
            self._timestamps.append(time.monotonic())


# ── Auth ───────────────────────────────────────────────────────

def _sign(method: str, path: str, body: str,
          api_key: str, api_secret: str) -> Dict[str, str]:
    """Return signed headers for a private API call."""
    timestamp = str(int(time.time()))
    message = timestamp + method + path + body
    signature = hmac.new(
        api_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {
        "ACCESS-KEY": api_key,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-SIGN": signature,
        "Content-Type": "application/json",
    }


# ── Main Client ────────────────────────────────────────────────

class BitFlyerClient:
    """
    BitFlyer HTTP API client.

    Args:
        api_key: BitFlyer API key (defaults to env BITFLYER_API_KEY).
        api_secret: BitFlyer API secret (defaults to env BITFLYER_API_SECRET).
        timeout: HTTP request timeout in seconds.
        dry_run: If True, skip private order placement (paper trading).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        timeout: float = 10.0,
        dry_run: bool = True,
    ) -> None:
        self.api_key = api_key or os.environ.get("BITFLYER_API_KEY", "")
        self.api_secret = api_secret or os.environ.get("BITFLYER_API_SECRET", "")
        self.timeout = timeout
        self.dry_run = dry_run
        self._session = requests.Session()
        self._session.headers.update({"Accept": "application/json"})
        self._rate = RateLimiter()

    # ── Internal helpers ───────────────────────────────────────

    def _get(self, path: str, params: Optional[Dict] = None) -> Any:
        """GET public endpoint."""
        self._rate.wait()
        url = BASE_URL + path
        try:
            r = self._session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.error("GET %s failed: %s", path, e)
            raise

    def _private(self, method: str, path: str,
                 body: Optional[Dict] = None) -> Any:
        """Authenticated private API call."""
        if not self.api_key or not self.api_secret:
            raise EnvironmentError(
                "BITFLYER_API_KEY and BITFLYER_API_SECRET must be set"
            )
        self._rate.wait()
        body_str = json.dumps(body) if body else ""
        headers = _sign(method, path, body_str, self.api_key, self.api_secret)
        url = BASE_URL + path
        try:
            if method == "GET":
                r = self._session.get(url, headers=headers, timeout=self.timeout)
            else:
                r = self._session.post(url, headers=headers, data=body_str,
                                       timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            logger.error("%s %s failed: %s", method, path, e)
            raise

    # ── Public endpoints ───────────────────────────────────────

    def get_ticker(self, product_code: str = "BTC_JPY") -> Dict:
        """Fetch current ticker for a product.

        Args:
            product_code: "BTC_JPY" or "FX_BTC_JPY".

        Returns:
            dict with best_bid, best_ask, ltp, volume, etc.
        """
        return self._get("/ticker", {"product_code": product_code})

    def get_board(self, product_code: str = "BTC_JPY") -> Dict:
        """Fetch order book (board) snapshot.

        Args:
            product_code: "BTC_JPY" or "FX_BTC_JPY".

        Returns:
            dict with mid_price, bids, asks lists.
        """
        return self._get("/board", {"product_code": product_code})

    def get_executions(
        self,
        product_code: str = "BTC_JPY",
        count: int = 500,
        before: Optional[int] = None,
        after: Optional[int] = None,
    ) -> List[Dict]:
        """Fetch recent executions (trades).

        Args:
            product_code: "BTC_JPY" or "FX_BTC_JPY".
            count: Max records (1-500).
            before: Fetch records with id < before (for pagination).
            after: Fetch records with id > after.

        Returns:
            List of execution dicts: id, side, price, size, exec_date.
        """
        params: Dict[str, Any] = {
            "product_code": product_code,
            "count": min(count, 500),
        }
        if before is not None:
            params["before"] = before
        if after is not None:
            params["after"] = after
        return self._get("/executions", params)

    def get_both_tickers(self) -> Dict[str, Dict]:
        """Fetch tickers for both BTC_JPY and FX_BTC_JPY simultaneously.

        Returns:
            dict with keys "spot" and "fx".
        """
        spot = self.get_ticker("BTC_JPY")
        fx = self.get_ticker("FX_BTC_JPY")
        return {"spot": spot, "fx": fx}

    def get_sfd_divergence(self) -> Dict:
        """Calculate current SFD divergence.

        SFD = (FX_ltp - Spot_ltp) / Spot_ltp * 100

        Returns:
            dict with spot_price, fx_price, divergence_pct, timestamp.
        """
        tickers = self.get_both_tickers()
        spot_price = float(tickers["spot"]["ltp"])
        fx_price = float(tickers["fx"]["ltp"])
        divergence = (fx_price - spot_price) / spot_price * 100
        return {
            "spot_price": spot_price,
            "fx_price": fx_price,
            "divergence_pct": round(divergence, 4),
            "timestamp": time.time(),
        }

    # ── Private endpoints ──────────────────────────────────────

    def get_balance(self) -> List[Dict]:
        """Fetch account balances.

        Returns:
            List of dicts: currency_code, amount, available.
        """
        return self._private("GET", "/me/getbalance")

    def send_child_order(
        self,
        product_code: str,
        child_order_type: str,
        side: str,
        price: Optional[float],
        size: float,
        minute_to_expire: int = 10080,
        time_in_force: str = "GTC",
    ) -> Dict:
        """Place a child order.

        Args:
            product_code: "BTC_JPY" or "FX_BTC_JPY".
            child_order_type: "LIMIT" or "MARKET".
            side: "BUY" or "SELL".
            price: Limit price (ignored for MARKET).
            size: Order size in BTC.
            minute_to_expire: Expiry in minutes.
            time_in_force: "GTC", "IOC", or "FOK".

        Returns:
            dict with child_order_acceptance_id.
        """
        if self.dry_run:
            logger.info(
                "[DRY RUN] Would send order: %s %s %s %.4f BTC @ %s",
                product_code, side, child_order_type, size, price,
            )
            return {"child_order_acceptance_id": f"DRY_RUN_{int(time.time())}"}

        body: Dict[str, Any] = {
            "product_code": product_code,
            "child_order_type": child_order_type,
            "side": side,
            "size": size,
            "minute_to_expire": minute_to_expire,
            "time_in_force": time_in_force,
        }
        if child_order_type == "LIMIT" and price is not None:
            body["price"] = int(price)

        return self._private("POST", "/me/sendchildorder", body)

    def cancel_child_order(
        self,
        product_code: str,
        child_order_acceptance_id: str,
    ) -> None:
        """Cancel an open child order."""
        body = {
            "product_code": product_code,
            "child_order_acceptance_id": child_order_acceptance_id,
        }
        self._private("POST", "/me/cancelchildorder", body)

    def get_child_orders(
        self,
        product_code: str = "FX_BTC_JPY",
        child_order_state: str = "ACTIVE",
        count: int = 100,
    ) -> List[Dict]:
        """Fetch open child orders."""
        return self._private(
            "GET",
            f"/me/getchildorders?product_code={product_code}"
            f"&child_order_state={child_order_state}&count={count}",
        )

    def get_positions(self, product_code: str = "FX_BTC_JPY") -> List[Dict]:
        """Fetch open FX positions.

        Returns:
            List of position dicts: side, size, price, sfd, pnl.
        """
        return self._private(
            "GET",
            f"/me/getpositions?product_code={product_code}",
        )


# ── WebSocket Ticker Stream ────────────────────────────────────

class TickerStream:
    """
    Real-time ticker feed via WebSocket (falls back to polling).

    Usage:
        stream = TickerStream(on_tick=my_callback)
        stream.start()
        # callback receives: {"spot": {...}, "fx": {...}, "divergence_pct": X}
        stream.stop()
    """

    CHANNEL_SPOT = "lightning_ticker_BTC_JPY"
    CHANNEL_FX = "lightning_ticker_FX_BTC_JPY"
    WS_URL = "wss://ws.lightstream.bitflyer.com/json-rpc"

    def __init__(
        self,
        on_tick: Callable[[Dict], None],
        poll_interval: float = 5.0,
        client: Optional[BitFlyerClient] = None,
    ) -> None:
        self.on_tick = on_tick
        self.poll_interval = poll_interval
        self.client = client or BitFlyerClient()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tickers: Dict[str, Dict] = {}

    def start(self) -> None:
        """Start the ticker stream (WebSocket preferred, polling fallback)."""
        self._running = True
        try:
            import websockets  # noqa: F401
            self._thread = threading.Thread(
                target=self._ws_loop, daemon=True, name="TickerWS"
            )
        except ImportError:
            logger.warning("websockets not available — using polling fallback")
            self._thread = threading.Thread(
                target=self._poll_loop, daemon=True, name="TickerPoll"
            )
        self._thread.start()
        logger.info("TickerStream started")

    def stop(self) -> None:
        """Stop the ticker stream."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("TickerStream stopped")

    def _emit(self, product: str, data: Dict) -> None:
        """Store tick and emit combined event if both products available."""
        self._tickers[product] = data
        if len(self._tickers) == 2:
            spot = self._tickers.get("BTC_JPY", {})
            fx = self._tickers.get("FX_BTC_JPY", {})
            s_ltp = float(spot.get("ltp", 0) or 0)
            f_ltp = float(fx.get("ltp", 0) or 0)
            div = (f_ltp - s_ltp) / s_ltp * 100 if s_ltp else 0.0
            try:
                self.on_tick({
                    "spot": spot,
                    "fx": fx,
                    "divergence_pct": round(div, 4),
                    "timestamp": time.time(),
                })
            except Exception as e:
                logger.error("on_tick callback error: %s", e)

    def _ws_loop(self) -> None:
        """WebSocket event loop (runs in thread)."""
        import asyncio
        import websockets as ws

        async def _run():
            while self._running:
                try:
                    async with ws.connect(self.WS_URL) as sock:
                        # Subscribe to both channels
                        for ch in [self.CHANNEL_SPOT, self.CHANNEL_FX]:
                            await sock.send(json.dumps({
                                "method": "subscribe",
                                "params": {"channel": ch},
                            }))
                        while self._running:
                            try:
                                raw = await asyncio.wait_for(sock.recv(), timeout=30)
                                msg = json.loads(raw)
                                ch = msg.get("params", {}).get("channel", "")
                                tick = msg.get("params", {}).get("message", {})
                                if "BTC_JPY" in ch and "FX" not in ch:
                                    self._emit("BTC_JPY", tick)
                                elif "FX_BTC_JPY" in ch:
                                    self._emit("FX_BTC_JPY", tick)
                            except asyncio.TimeoutError:
                                pass
                except Exception as e:
                    if self._running:
                        logger.warning("WS error, reconnecting: %s", e)
                        await asyncio.sleep(3)

        loop = asyncio.new_event_loop()
        loop.run_until_complete(_run())
        loop.close()

    def _poll_loop(self) -> None:
        """Polling fallback when WebSocket unavailable."""
        while self._running:
            try:
                data = self.client.get_sfd_divergence()
                self.on_tick(data)
            except Exception as e:
                logger.error("Poll error: %s", e)
            time.sleep(self.poll_interval)
