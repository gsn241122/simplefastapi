from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import Base, engine
from app.core.dependencies import request_logger
from app.modules.user.routes import router as user_router
from app.modules.product.routes import router as product_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FastAPI App",
    description="Simple FastAPI with User and Product Management",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    return await request_logger(request, call_next)

# Include routers
app.include_router(user_router)
app.include_router(product_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI App"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
