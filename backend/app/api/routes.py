"""FastAPI application assembly for the modular TMS application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..db.schema import init_db, seed
from .auth import router as auth_router
from .billing import router as billing_router
from .customers import router as customers_router
from .exceptions import router as exceptions_router
from .notifications import router as notifications_router
from .orders import router as orders_router
from .parcels import router as parcels_router
from .tasks import router as tasks_router


app = FastAPI(title="TMS API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    seed()


app.include_router(auth_router)
app.include_router(parcels_router)
app.include_router(orders_router)
app.include_router(tasks_router)
app.include_router(exceptions_router)
app.include_router(billing_router)
app.include_router(notifications_router)
app.include_router(customers_router)
