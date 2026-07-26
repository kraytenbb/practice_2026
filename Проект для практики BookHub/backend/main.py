from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from database import Base, engine
from routes import router


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BookHub",
    version="0.2.0"
)

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)

app.include_router(router)
