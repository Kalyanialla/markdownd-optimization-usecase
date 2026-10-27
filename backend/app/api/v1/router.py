"""
Main API v1 router mounting all modular endpoint routers.
"""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    auth,
    users,
    products,
    optimization,
    recommendations,
    policies,
    audit,
    dashboard,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(products.router)
api_router.include_router(optimization.router)
api_router.include_router(recommendations.router)
api_router.include_router(policies.router)
api_router.include_router(audit.router)
api_router.include_router(dashboard.router)
