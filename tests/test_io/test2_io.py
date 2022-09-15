IMPORT_BATCHES = [
    {
        "items": [
            {
                "type": "FILE",
                "id": "a",
                "parentId": "A",
                "url": "file1",
                "size": 123
            },
            {
                "id": "A",
                "type": "FOLDER"
            }
        ],
        "updateDate": "2022-02-01T12:00:00.000Z"
    }
]

EXPECTED_TREE = {
    "type": "FOLDER",
    "id": "A",
    "size": 123,
    "url": None,
    "parentId": None,
    "date": "2022-02-01T12:00:00Z",
    "children": [
        {
            "type": "FILE",
            "id": "a",
            "parentId": "A",
            "size": 123,
            "url": "file1",
            "date": "2022-02-01T12:00:00Z",
            "children": None
        }
    ]
}