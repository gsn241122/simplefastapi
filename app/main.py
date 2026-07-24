from fastapi import FastAPI
from app.core.database import Base, engine
from app.modules.user.routes import router as user_router
from app.modules.product.routes import router as product_router

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="FastAPI App",
    description="Simple FastAPI with User and Product Management",
    version="1.0.0"
)

# Include routers
app.include_router(user_router)
app.include_router(product_router)


@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI App"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
