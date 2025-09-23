from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)
PUBLIC_DIR = os.path.join(BASE_DIR, "public")

app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

@app.get("/")
def index():
    return FileResponse(os.path.join(PUBLIC_DIR, "index.html"))
