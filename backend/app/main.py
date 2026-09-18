from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import chat, recommend

settings = get_settings()

app = FastAPI(title="CIMET Hackathon API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(recommend.router, prefix="/api/recommend", tags=["recommend"])


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
