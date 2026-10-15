from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Dict, Any, List, Optional
from decimal import Decimal, ROUND_HALF_UP
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

router = APIRouter()

@router.get("/dashboard/properties")
async def get_dashboard_properties(
    current_user: dict = Depends(get_current_user)
) -> List[Dict[str, Any]]:
    from app.services.reservations import get_tenant_properties

    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")

    try:
        return await get_tenant_properties(tenant_id)
    except Exception:
        raise HTTPException(status_code=503, detail="Property data is temporarily unavailable")

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: Optional[int] = Query(None, ge=1, le=12),
    year: Optional[int] = Query(None, ge=2000, le=2100),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="No tenant associated with this user")
    
    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id, month=month, year=year)
    except Exception:
        raise HTTPException(status_code=503, detail="Revenue data is temporarily unavailable")
    
    # Round to cents with Decimal before converting, so float artefacts never reach clients
    total_revenue = Decimal(revenue_data['total']).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_revenue_float = float(total_revenue)
    
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
