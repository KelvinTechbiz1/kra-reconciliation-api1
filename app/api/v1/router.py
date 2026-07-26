from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.company import router as company_router
from app.api.v1.import_profiles import router as import_profiles_router
from app.api.v1.purchases import router as purchases_router
from app.api.v1.reconciliation import router as reconciliation_router
from app.api.v1.sales import router as sales_router
from app.api.v1.sessions import router as sessions_router
from app.api.v1.settings import router as settings_router
from app.api.v1.templates import router as templates_router
from app.api.v1.users import router as users_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(sales_router)
router.include_router(purchases_router)
router.include_router(reconciliation_router)
router.include_router(sessions_router)
router.include_router(templates_router)
router.include_router(settings_router)
router.include_router(users_router)
router.include_router(company_router)
router.include_router(import_profiles_router)

