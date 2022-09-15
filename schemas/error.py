from fastapi import status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


def error404():
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=jsonable_encoder({"code": 404, "message": "Item not found"}))


def error400():
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({"code": 400, "message": "Validation Error"}))
