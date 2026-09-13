import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.middleware.error_handler import register_exception_handlers
from app.middleware.rate_limiter import limiter
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes import auth_routes, blood_request_routes, dashboard_routes, user_routes

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(
    title=settings.APP_NAME,
    description="REST API powering the Blood Donor-Recipient Connection Platform.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---- Rate limiting ----
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# ---- Security headers ----
app.add_middleware(SecurityHeadersMiddleware)

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Global exception handlers ----
register_exception_handlers(app)

# ---- Routers ----
app.include_router(auth_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(user_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(blood_request_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(dashboard_routes.router, prefix=settings.API_V1_PREFIX)


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"success": True, "message": "OK", "environment": settings.ENVIRONMENT}
