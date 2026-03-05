from aiogram import Router
from .start import router as start_router
from .filter_cc import router as filter_router
from .co import router as co_router
from .proxy_cmd import router as proxy_router
from .admin import router as admin_router

router = Router()
router.include_router(start_router)
router.include_router(proxy_router)
router.include_router(co_router)
router.include_router(filter_router)
router.include_router(admin_router)
