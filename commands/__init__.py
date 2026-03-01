from aiogram import Router
from .start import router as start_router
from .filter_cc import router as filter_router
from .co import router as co_router

router = Router()
router.include_router(start_router)
router.include_router(filter_router)
router.include_router(co_router)
