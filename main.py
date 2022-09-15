import uvicorn
from envparse import Env
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import APIRouter, FastAPI, status, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder

from api.v1 import (create_nodes, get_node, delete_node, get_history, get_updates)


env = Env()
MONGODB_URL = env.str("MONGODB_URL", default="mongodb://localhost:27017/nodes")


routes = [
    APIRoute(path="/imports", endpoint=create_nodes, methods=["POST"], tags=["Базовые задачи"]),
    APIRoute(path="/nodes/{id}", endpoint=get_node, methods=["GET"], tags=["Базовые задачи"]),
    APIRoute(path="/delete/{id}", endpoint=delete_node, methods=["DELETE"], tags=["Базовые задачи"]),

    APIRoute(path="/updates", endpoint=get_updates, methods=["GET"], tags=["Дополнительные задачи"]),
    APIRoute(path="/node/{id}/history", endpoint=get_history, methods=["GET"], tags=["Дополнительные задачи"])
]

client = AsyncIOMotorClient(MONGODB_URL)
app = FastAPI(title="Yandex Backend School 2022 Test Task", 
              version="1.0", 
              description="Практическое задание отбора в Школу Бэкенд Разработки 2022")
app.state.mongo_client = client

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, ecx: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({"code": 400, "message": "Validation error"}))

app.include_router(APIRouter(routes=routes))


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=80)
