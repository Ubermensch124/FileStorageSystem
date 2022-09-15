from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Request

from schemas.error import error404


async def delete_node(id, date: datetime, request: Request):
    """
    Удаляет ноду с id из базы данных
    """
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]
    element = await mongo_client.records.find_one({"id": id})

    if not element:
        return error404()

    async def rec_delete(ID):
        elem = await mongo_client.records.find_one({"id": ID})
        if elem["type"] == 'FOLDER':
            for child in elem["children"]:     
                await rec_delete(ID=child)
        await mongo_client.records.delete_one({"id": ID})
        await mongo_client.updates.delete_one({"id": ID})

    await rec_delete(ID=id)
    return {"Response": "Successful"}