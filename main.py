from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

@app.get("/")
def home():
    return {"Message": "Hospital Support Request System"}


db = {
    1: {"id": 1,
        "title": "Patient Monitor Not Working",
        "description": "The patient monitor in Ward 2 is not turning on",
        "category": "EQUIPMENT_ISSUE",
        "department": "Nursing",
        "status": "NEW"},
    2: {"id": 2,
        "title": "Air Conditioner Not Working",
        "description": "The air conditioner in the ICU is not functioning",
        "category": "FACILITY_REQUEST",
        "department": "ICU",
        "status": "NEW"}
}

#Schemas
class RequestCreate(BaseModel):
    title : str
    description : str
    category : str
    status : str
    
class RequestResponse(RequestCreate):
    id : int

#APIs
@app.get("/requests")
def request_read_all():
    return list(db.values())

@app.get("/requests/{id}")
def request_read_by_id(id: int):
    if id not in db:
        raise HTTPException(
            detail="Support request not found",
            status_code=404
        )
    return db[id]

@app.post("/requests", status_code=201, response_model=RequestResponse)
def request_create(request_payload : RequestCreate):
    new_id = max(db.keys(), default=0) + 1
    db[new_id] = {"id" : new_id, **request_payload.model_dump()}
    return db[new_id]

@app.put("/requests/{id}", response_model=RequestResponse)
def request_update(id : int, payload : RequestCreate):
    if id not in db:
        raise HTTPException(detail="Request Not Found", status_code=404)
    db[id] = {"id" : id, **payload.model_dump()}
    return db[id]

@app.delete("requests/{id}")
def request_delete(id : int):
    if id not in db:
        raise HTTPException(detail="Request Not Found", status_code=404)
    del db[id]
    return {"Message" : "Request Deleted Successfully"}

