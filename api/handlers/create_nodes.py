from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Request

from schemas.create import CreateSchema
from schemas.error import error400


async def create_nodes(data: CreateSchema, request: Request):
    """
    Создаём ноды из списка items: [...]    
    """
    mongo_client: AsyncIOMotorClient = request.app.state.mongo_client["nodes"]

    array = data.items
    date = data.updateDate
    if isinstance(date, datetime):
        date = date.isoformat(sep='T', timespec='seconds')[:-6] + "Z"

    id_set = set()
    parent_uchet = set()     
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
        """
        Обновление по цепочке значений для всех предков
        Item -> родитель Item -> родитель родителя Item -> ...
        """
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
        """
        Если переданный элемент абсолютно новый, но имеет parentId,
        проверяем, существует ли элемент с id = parentId
        """
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

        if not last_version and item.parentId:              
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
            result = dict(list(list(last_version.items()) + list(item.dict().items())))  
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

        if not updates_collection:
            if result.get('_id'):
                del result['_id']
            if result.get('children'):
                del result["children"]
            await mongo_client.updates.insert_one({"id": result["id"], "updateList": [date], "updateView": [result]})
        else:    
            updateList = updates_collection["updateList"]
            viewList = updates_collection["updateView"]
            if not updateList or (updateList and updateList[-1] != date):
                updateList.append(date)
                if result.get('children'):
                    del result["children"]
                if result.get('_id'):
                    del result['_id']
                viewList.append(result)
                await mongo_client.updates.update_one({"id": result["id"]}, {"$set": {"updateList": updateList}})
                await mongo_client.updates.update_one({"id": result["id"]}, {"$set": {"updateView": viewList}})

    return {"Success": True}