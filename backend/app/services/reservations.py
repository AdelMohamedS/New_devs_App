from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, List, Optional

def _month_bounds(month: int, year: int):
    """Naive [start, end) bounds of a calendar month, interpreted in the property's local time."""
    start_date = datetime(year, month, 1)
    if month < 12:
        end_date = datetime(year, month + 1, 1)
    else:
        end_date = datetime(year + 1, 1, 1)
    return start_date, end_date

async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int) -> Decimal:
    """
    Calculates revenue for a specific month, using the property's local timezone.
    """
    result = await calculate_total_revenue(property_id, tenant_id, month=month, year=year)
    return Decimal(result["total"])

async def calculate_total_revenue(
    property_id: str, tenant_id: str, month: Optional[int] = None, year: Optional[int] = None
) -> Dict[str, Any]:
    """
    Aggregates revenue from database, optionally for a single month.
    Month boundaries follow the property's timezone, not UTC.
    """
    try:
        # Reuse the shared database pool, initializing it once
        from app.core.database_pool import db_pool
        
        if not db_pool.session_factory:
            await db_pool.initialize()
        
        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                params = {"property_id": property_id, "tenant_id": tenant_id}
                period_filter = ""
                if month and year:
                    # Convert check-in to property-local time before comparing with month bounds
                    params["start_date"], params["end_date"] = _month_bounds(month, year)
                    period_filter = """
                        AND (r.check_in_date AT TIME ZONE p.timezone) >= :start_date
                        AND (r.check_in_date AT TIME ZONE p.timezone) < :end_date
                    """
                
                query = text(f"""
                    SELECT 
                        r.property_id,
                        SUM(r.total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations r
                    JOIN properties p ON p.id = r.property_id AND p.tenant_id = r.tenant_id
                    WHERE r.property_id = :property_id AND r.tenant_id = :tenant_id
                    {period_filter}
                    GROUP BY r.property_id
                """)
                
                result = await session.execute(query, params)
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception as e:
        print(f"Database error for {property_id} (tenant: {tenant_id}): {e}")
        # Never fall back to made-up figures: surface the failure instead
        raise
