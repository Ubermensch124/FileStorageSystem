from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Request

from schemas.error import error404


async def get_node(id, request: Request):
    """
    Получаем структурированную ноду
    """
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]
    element = await mongo_client.records.find_one({"id": id})
    if not element:
        return error404()

    async def rec_draw(ID):
        elem = await mongo_client.records.find_one({"id": ID})
        del elem["_id"]
        if not elem.get('children'):
            elem["children"] = None
        if elem["type"] == 'FOLDER' and not elem.get('children'):
            elem["size"] = None
        
        if elem["type"] == 'FOLDER' and elem["children"]:
            ans = []
            for child in elem["children"]:     
                res = await rec_draw(ID=child)
                ans.append(res)
            elem["children"] = ans

        return elem
    
    return await rec_draw(ID=id)