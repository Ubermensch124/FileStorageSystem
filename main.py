from datetime import datetime, timedelta
from bisect import bisect_left

from envparse import Env
import uvicorn
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import APIRouter, FastAPI, status, Request
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder

from schemas import CreateSchema


env = Env()
MONGODB_URL = env.str("MONGODB_URL", default="mongodb://localhost:27017/nodes")


def error404():
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=jsonable_encoder({"code": 404, "message": "Item not found"}))


def error400():
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({"code": 400, "message": "Validation Error"}))


async def get_node(id, request: Request):
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]
    element = await mongo_client.records.find_one({"id": id})
    if not element:
        return error404()

    async def rec_draw(ID):
        elem = await mongo_client.records.find_one({"id": ID})
        del elem["_id"]
        if not elem.get('children'):
            elem["children"] = None
        
        if elem["type"] == 'FOLDER' and elem["children"]:
            ans = []
            for child in elem["children"]:     # итерируемся по индексам детей
                res = await rec_draw(ID=child)
                ans.append(res)
            elem["children"] = ans

        return elem    

    answer = await rec_draw(ID=id)
    return answer


async def create_nodes(data: CreateSchema, request: Request):
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]

    array = data.items
    date = data.updateDate
    if isinstance(date, datetime):
        date = date.isoformat(sep='T', timespec='seconds')[:-6] + "Z"

    id_set = set()
    parent_uchet = set()    # сюда складываем все папки с items, которые посетили 
    parent_under_control = set()

    for item in array:
        condition = (
            item.id in id_set,
            item.type == 'FOLDER' and item.size is not None,
            item.type == 'FOLDER' and item.url is not None,
            item.type == 'FILE' and item.size is None,
            item.type == 'FILE' and item.url is None
        )

        if any(condition):
            return error400()
        
        if item.parentId is not None:
            res = await mongo_client.records.find_one({"id": item.parentId})
            if res is not None and res["type"] != 'FOLDER':
                return error400()
            elif res is None and item.parentId not in parent_uchet:
                parent_under_control.add(item.parentId)

        last_version = await mongo_client.records.find_one({"id": item.id})
        if last_version:
            if item.type != last_version["type"]:
                return error400()
        
        id_set.add(item.id)
        if item.type == 'FOLDER':
            parent_uchet.add(item.id)
            if item.id in parent_under_control:
                parent_under_control.remove(item.id)

    if parent_under_control:
        return error400()


    async def update_parent_loop(diff, parent, mode=None, item_id=None):
        child = parent["children"]
        if mode:
            child.remove(item_id) if mode=='Delete' else child.append(item_id)
        await mongo_client.records.update_one({"id": parent["id"]}, {"$set": {"children": child}})
        while parent:
            if diff:
                new_size = parent["size"] + diff
                await mongo_client.records.update_one({"id": parent["id"]}, {"$set": {"size": new_size}})

            upd_parent = await mongo_client.updates.find_one({"id": parent["id"]})
            updlist = upd_parent["updateList"]
            updview = upd_parent["updateView"]

            if updlist[-1] == date:
                updlist.pop()
                updview.pop()

            updlist.append(date)
            await mongo_client.updates.update_one({"id": parent["id"]}, {"$set": {"updateList": updlist}})
            await mongo_client.records.update_one({"id": parent["id"]}, {"$set": {"date": date}})

            folder = await mongo_client.records.find_one({"id": parent["id"]})
            del folder["children"]
            del folder["_id"]
            updview.append(folder)
            await mongo_client.updates.update_one({"id": parent["id"]}, {"$set": {"updateView": updview}})

            if parent['parentId']:
                parent = await mongo_client.records.find_one({"id": parent["parentId"]})
            else:
                parent = None


    async def check_exist_parent(item, last_vers):
        diff = None
        if item.size:
            diff = item.size
        elif last_vers and last_vers['parentId'] is not None:
            diff = last_vers['size']

        parent = await mongo_client.records.find_one({"id": item.parentId})
        if not parent:
            folder = {"id": item.parentId, "type": "FOLDER", "size": diff, "children": [item.id], "date": date, "url": None}
            await mongo_client.records.insert_one(folder)
        else:
            await update_parent_loop(diff=diff, parent=parent, mode='Append', item_id=item.id)


    for item in array:
        last_version = await mongo_client.records.find_one({"id": item.id})

        if not last_version and item.parentId:               # если элемент новый, но имеет родителя
            await check_exist_parent(item=item, last_vers=last_version)
        elif last_version:
            if last_version.get('parentId') is not None:
                if item.parentId and item.parentId == last_version["parentId"]:
                    diff = None
                    if item.size:
                        diff = item.size - last_version["size"]
                    parent = await mongo_client.records.find_one({"id": item.parentId})
                    await update_parent_loop(diff=diff, parent=parent)

                elif item.parentId and item.parentId != last_version["parentId"]:
                    diff = None
                    if item.size:
                        diff = -item.size
                    elif last_version["size"]:
                        diff = -last_version["size"]
                    parent = await mongo_client.records.find_one({"id": last_version["parentId"]})
                    await update_parent_loop(diff=diff, parent=parent, mode='Delete', item_id=item.id)

                    if diff:
                        diff = +diff
                    parent = await mongo_client.records.find_one({"id": item.parentId})
                    await update_parent_loop(diff=diff, parent=parent, mode='Append', item_id=item.id)

                elif item.parentId is None:
                    diff = None
                    if item.size:
                        diff = -item.size
                    elif last_version["size"]:
                        diff = -last_version["size"]
                    parent = await mongo_client.records.find_one({"id": last_version["parentId"]})
                    await update_parent_loop(diff=diff, parent=parent, mode='Delete', item_id=item.id)

            elif last_version.get('parentId') is None and item.parentId is not None:
                await check_exist_parent(item=item, last_vers=last_version)


        if last_version:
            result = dict(list(list(last_version.items()) + list(item.dict().items())))    # старые значения перезапишутся, новые добавятся
            del result['_id']
        else:
            result = item.dict()

        result["date"] = date

        if last_version and last_version["type"] == "FOLDER":
            result["size"] = last_version["size"]
        elif not last_version and result['type'] == 'FOLDER':
            result['size'] = 0
            result['children'] = []
        
        updates_collection = await mongo_client.updates.find_one({"id": result["id"]})
        if last_version:
            await mongo_client.records.delete_one({"id": result['id']})
            await mongo_client.records.insert_one(result)
        elif not last_version or (last_version and not updates_collection):
            await mongo_client.records.insert_one(result)
            if result.get('children') is not None:
                del result['children']
            if result.get('_id'):
                del result['_id']
            await mongo_client.updates.insert_one({"id": result["id"], "updateList": [date], "updateView": [result]})
            continue
        
        if updates_collection:
            updateList = updates_collection["updateList"]
            viewList = updates_collection["updateView"]
            if updateList[-1] != date:
                updateList.append(date)
                if result.get('children'):
                    del result["children"]
                if result.get('_id'):
                    del result['_id']
                viewList.append(result)
                await mongo_client.updates.update_one({"id": result["id"]}, {"$set": {"updateList": updateList}})
                await mongo_client.updates.update_one({"id": result["id"]}, {"$set": {"updateView": viewList}})

    return {"Success": True}


async def delete_node(id, date: datetime, request: Request):
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]
    element = await mongo_client.records.find_one({"id": id})

    if not element:
        return error404()

    async def rec_delete(ID):
        elem = await mongo_client.records.find_one({"id": ID})
        if elem["type"] == 'FOLDER':
            for child in elem["children"]:     # итерируемся по индексам детей
                await rec_delete(ID=child)
        await mongo_client.records.delete_one({"id": ID})
        await mongo_client.updates.delete_one({"id": ID})

    await rec_delete(ID=id)
    return {"Response": "Successful"}


async def get_updates(date: datetime, request: Request):
    """
    Все элементы, которые были обновлены за последние 24 часа от даты
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


async def get_history(id, dateStart: datetime, dateEnd: datetime, request: Request):
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]

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
            result.append(view_item) 

    return {"items": result}


routes = [
    APIRoute(path="/imports", endpoint=create_nodes, methods=["POST"], tags=["Базовые задачи"]),
    APIRoute(path="/nodes/{id}", endpoint=get_node, methods=["GET"], tags=["Базовые задачи"]),
    APIRoute(path="/delete/{id}", endpoint=delete_node, methods=["DELETE"], tags=["Базовые задачи"]),

    APIRoute(path="/updates", endpoint=get_updates, methods=["GET"], tags=["Дополнительные задачи"]),
    APIRoute(path="/node/{id}/history", endpoint=get_history, methods=["GET"], tags=["Дополнительные задачи"])
]

client = AsyncIOMotorClient(MONGODB_URL)
app = FastAPI(title="Yandex Backend School 2022 Test Task", version="1.0")
app.state.mongo_client = client

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, ecx: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({"code": 400, "message": "Validation error"}))

app.include_router(APIRouter(routes=routes))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
