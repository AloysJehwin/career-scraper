"""Lambda handler — Mangum ASGI adapter for the FastAPI app."""

from mangum import Mangum

from career_scraper.api import app

handler = Mangum(app, lifespan="off")
