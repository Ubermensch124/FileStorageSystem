from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Request
from datetime import datetime, timedelta
from bisect import bisect_left


async def get_updates(date: datetime, request: Request):
    """
    Все элементы, которые были обновлены за последние 24 часа от даты - [date-24h, date]
    """
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]
    date_start: datetime = date - timedelta(days=1)


    start = date_start.isoformat(sep='T', timespec='seconds')[:-6] + 'Z'
    end = date.isoformat(sep='T', timespec='seconds')[:-6] + 'Z' 

    result = []

    cursor = mongo_client.updates.find({})
    async for item in cursor:
        date_list = item["updateList"]
        insert_ind = bisect_left(date_list, end)
        if start <= date_list[insert_ind - int(insert_ind/len(date_list))] <= end:
            view_list = item["updateView"]
            res = view_list[insert_ind - int(insert_ind/len(date_list))]
            if res.get('_id'):
                del res['_id']
            result.append(res)

    return {"items": result}