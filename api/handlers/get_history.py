from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Request

from schemas.error import error404


async def get_history(id, dateStart: datetime, dateEnd: datetime, request: Request):
    """
    Все версии элемента с id, за [dateStart, dateEnd)
    """
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]

    elem = await mongo_client.records.find_one({"id": id})
    if not elem:
        return error404()

    start = dateStart.isoformat(sep='T', timespec='seconds')[:-6] + 'Z'
    end = dateEnd.isoformat(sep='T', timespec='seconds')[:-6] + 'Z' 

    result = []

    cursor = await mongo_client.updates.find_one({"id": id})
    viewList = cursor["updateView"]
    updList = cursor["updateList"]
    for ID, item in enumerate(updList):
        if start <= item < end: 
            view_item = viewList[ID]
            if view_item.get('_id'):
                del view_item["_id"]
            if view_item.get('size') == 0:
                view_item["size"] = None
            result.append(view_item) 

    return {"items": result}