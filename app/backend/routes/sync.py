"""
Alpaca Sync Service - Keeps local trade history in sync with Alpaca
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

router = APIRouter(prefix="/sync", tags=["Alpaca Sync"])
logger = logging.getLogger(__name__)


def get_alpaca_service():
    """Get Alpaca service instance."""
    from src.trading.alpaca_service import AlpacaService
    return AlpacaService()


@router.post("/orders")
async def sync_orders_from_alpaca(
    days: int = 30,
    calculate_pnl: bool = True
):
    """
    Sync filled orders from Alpaca into local trade_history.
    
    - Fetches all closed orders from Alpaca (last N days)
    - Imports any missing orders into trade_history
    - Optionally calculates realized P&L by matching buy/sell pairs
    
    This ensures our metrics (win rate, total trades) match Alpaca's records.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        alpaca = get_alpaca_service()
        
        # Fetch closed orders from Alpaca
        logger.info(f"Fetching closed orders from Alpaca (last {days} days)")
        filled_orders = alpaca.get_orders(status="closed", limit=500)
        
        imported = 0
        skipped = 0
        errors = []
        
        with engine.connect() as conn:
            for order in filled_orders:
                # Only import filled orders with actual fills
                if order.status != "filled" or not order.filled_qty or float(order.filled_qty) <= 0:
                    continue
                
                try:
                    # Check if already exists
                    check = conn.execute(
                        text("SELECT id FROM trade_history WHERE order_id = :oid"),
                        {"oid": order.id}
                    )
                    if check.fetchone():
                        skipped += 1
                        continue
                    
                    # Insert new trade
                    conn.execute(text("""
                        INSERT INTO trade_history 
                        (order_id, ticker, action, quantity, entry_price, status, entry_time, created_at)
                        VALUES (:order_id, :ticker, :action, :qty, :price, 'filled', :time, NOW())
                    """), {
                        "order_id": order.id,
                        "ticker": order.symbol,
                        "action": order.side,
                        "qty": float(order.filled_qty),
                        "price": float(order.filled_avg_price) if order.filled_avg_price else None,
                        "time": order.filled_at or order.submitted_at,
                    })
                    conn.commit()
                    imported += 1
                    logger.info(f"Imported: {order.symbol} {order.side} {order.filled_qty} @ ${order.filled_avg_price}")
                    
                except Exception as e:
                    errors.append(f"{order.id}: {str(e)[:50]}")
        
        # Calculate realized P&L if requested
        pnl_updates = 0
        if calculate_pnl:
            pnl_updates = await _calculate_realized_pnl()
        
        return {
            "success": True,
            "orders_found": len(filled_orders),
            "imported": imported,
            "skipped": skipped,
            "pnl_updates": pnl_updates,
            "errors": errors[:10] if errors else None,
        }
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _calculate_realized_pnl() -> int:
    """
    Calculate realized P&L by matching buy/sell pairs per ticker.
    Uses FIFO (First In, First Out) matching.
    
    Returns number of trades updated.
    """
    from sqlalchemy import text
    from app.backend.database.connection import engine
    
    updated = 0
    
    with engine.connect() as conn:
        # Get all tickers that have both buys and sells
        tickers_result = conn.execute(text("""
            SELECT DISTINCT ticker FROM trade_history 
            WHERE ticker IN (
                SELECT ticker FROM trade_history WHERE action = 'buy'
                INTERSECT
                SELECT ticker FROM trade_history WHERE action = 'sell'
            )
        """))
        tickers = [row[0] for row in tickers_result.fetchall()]
        
        for ticker in tickers:
            # Get all trades for this ticker ordered by time
            trades = conn.execute(text("""
                SELECT id, action, quantity, entry_price, status, entry_time
                FROM trade_history
                WHERE ticker = :ticker
                ORDER BY entry_time ASC
            """), {"ticker": ticker}).fetchall()
            
            # FIFO matching
            buys = []  # Queue of (id, remaining_qty, price)
            
            for trade in trades:
                trade_id, action, qty, price, status, entry_time = trade
                
                if action == 'buy':
                    buys.append([trade_id, float(qty), float(price) if price else 0])
                    
                elif action == 'sell' and buys and status != 'closed':
                    # Match against oldest buys
                    sell_qty = float(qty)
                    sell_price = float(price) if price else 0
                    total_cost_basis = 0
                    qty_matched = 0
                    
                    while sell_qty > 0 and buys:
                        buy_id, buy_remaining, buy_price = buys[0]
                        
                        match_qty = min(sell_qty, buy_remaining)
                        total_cost_basis += match_qty * buy_price
                        qty_matched += match_qty
                        sell_qty -= match_qty
                        buys[0][1] -= match_qty
                        
                        if buys[0][1] <= 0:
                            buys.pop(0)
                    
                    if qty_matched > 0:
                        avg_cost = total_cost_basis / qty_matched
                        realized_pnl = (sell_price - avg_cost) * qty_matched
                        return_pct = ((sell_price - avg_cost) / avg_cost) * 100 if avg_cost > 0 else 0
                        
                        # Update the sell trade
                        conn.execute(text("""
                            UPDATE trade_history
                            SET status = 'closed',
                                realized_pnl = :pnl,
                                return_pct = :ret_pct
                            WHERE id = :id
                        """), {
                            "id": trade_id,
                            "pnl": round(realized_pnl, 2),
                            "ret_pct": round(return_pct, 4),
                        })
                        conn.commit()
                        updated += 1
                        logger.info(f"P&L calculated for {ticker} sell: ${realized_pnl:.2f} ({return_pct:.2f}%)")
    
    return updated


@router.get("/status")
async def get_sync_status():
    """
    Get sync status - compare local trade count vs Alpaca order count.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        alpaca = get_alpaca_service()
        
        # Get Alpaca counts
        filled_orders = alpaca.get_orders(status="closed", limit=500)
        alpaca_count = len([o for o in filled_orders if o.status == "filled"])
        
        # Get local counts
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM trade_history WHERE order_id IS NOT NULL"))
            local_count = result.scalar()
            
            result = conn.execute(text("SELECT COUNT(*) FROM trade_history WHERE status = 'closed'"))
            closed_count = result.scalar()
        
        return {
            "success": True,
            "alpaca_filled_orders": alpaca_count,
            "local_synced_orders": local_count,
            "local_closed_trades": closed_count,
            "in_sync": alpaca_count == local_count,
            "message": "In sync" if alpaca_count == local_count else f"Missing {alpaca_count - local_count} orders",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recalculate-pnl")
async def recalculate_all_pnl():
    """
    Recalculate all realized P&L from scratch using FIFO matching.
    Useful after importing orders or fixing data.
    """
    try:
        from sqlalchemy import text
        from app.backend.database.connection import engine
        
        # Reset all closed statuses first
        with engine.connect() as conn:
            conn.execute(text("""
                UPDATE trade_history
                SET status = 'filled', realized_pnl = NULL, return_pct = NULL
                WHERE status = 'closed'
            """))
            conn.commit()
        
        # Recalculate
        updated = await _calculate_realized_pnl()
        
        return {
            "success": True,
            "trades_updated": updated,
            "message": f"Recalculated P&L for {updated} trades",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
