from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from pymongo import MongoClient
from bson import ObjectId

import jwt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from datetime import datetime, timedelta, timezone


app = FastAPI()


# MongoDB
URL = "mongodb://127.0.0.1:27017"
client = MongoClient(URL)

db = client["hospital_support_db"]

request_collection = db["support_requests"]
user_collection = db["users"]


# Security config
password_hash = PasswordHash.recommended()

SECRET_KEY = "HospitalSupportSecurityKey-ChangeThis"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINS = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


# -----------------------------
# Pydantic Models
# -----------------------------

# Hospital support request
class SupportRequestCreate(BaseModel):
    patient_name: str
    issue: str
    department: str
    priority: str
    status: str


class SupportRequestResponse(SupportRequestCreate):
    id: str


# Hospital user
class UserCreate(BaseModel):
    username: str
    password: str
    role: int


# Token
class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# -----------------------------
# Helper Functions
# -----------------------------

# Support request helper
def request_helper(request):
    return {
        "id": str(request["_id"]),
        "patient_name": request["patient_name"],
        "issue": request["issue"],
        "department": request["department"],
        "priority": request["priority"],
        "status": request["status"]
    }


# User helper
def user_helper(user):
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "role": user["role"]
        # 1 = Hospital Staff
        # 2 = Support Engineer
        # 3 = Department Head
        # 4 = Hospital Admin
    }


# -----------------------------
# JWT Token
# -----------------------------

def create_token(username: str, role: int):

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=TOKEN_EXPIRE_MINS
    )

    payload = {
        "sub": username,
        "role": role,
        "exp": expire
    }

    token = jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return token


# -----------------------------
# Get Current User
# -----------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme)
):

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )

        username = payload.get("sub")
        role = payload.get("role")

        if username is None or role is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    except jwt.ExpiredSignatureError:

        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )

    except jwt.InvalidTokenError:

        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )

    user = user_collection.find_one(
        {"username": username}
    )

    if user is None:

        raise HTTPException(
            status_code=404,
            detail="Hospital user not found"
        )

    return user


# -----------------------------
# Role Authorization
# -----------------------------

def require_roles(*allowed_roles):

    def check_role(
        current_user=Depends(get_current_user)
    ):

        if current_user["role"] not in allowed_roles:

            raise HTTPException(
                status_code=403,
                detail="Permission denied for this hospital role"
            )

        return current_user

    return check_role


# =====================================================
# USER APIs
# =====================================================


# Create hospital user
@app.post("/users", status_code=201)
def create_user(user: UserCreate):

    queried_user = user_collection.find_one(
        {"username": user.username}
    )

    if queried_user:

        raise HTTPException(
            status_code=409,
            detail="Hospital username already exists"
        )

    hashed_pwd = password_hash.hash(
        user.password
    )

    user_data = {
        "username": user.username,
        "password": hashed_pwd,
        "role": user.role
    }

    result = user_collection.insert_one(
        user_data
    )

    new_user = user_collection.find_one(
        {"_id": result.inserted_id}
    )

    return user_helper(new_user)


# Hospital user login
@app.post(
    "/login",
    response_model=TokenResponse
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends()
):

    user = user_collection.find_one(
        {"username": form_data.username}
    )

    if user is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid hospital username or password"
        )

    if not password_hash.verify(
        form_data.password,
        user["password"]
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid hospital username or password"
        )

    token = create_token(
        user["username"],
        user["role"]
    )

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# =====================================================
# HOSPITAL SUPPORT REQUEST APIs
# =====================================================


# Create support request
@app.post(
    "/support-requests",
    status_code=201,
    response_model=SupportRequestResponse
)
def create_support_request(
    payload: SupportRequestCreate,
    current_user=Depends(
        require_roles(1, 2, 3, 4)
    )
):

    request_dict = payload.model_dump()

    result = request_collection.insert_one(
        request_dict
    )

    new_request = request_collection.find_one(
        {"_id": result.inserted_id}
    )

    return request_helper(new_request)


# Get all hospital support requests
@app.get(
    "/support-requests",
    response_model=list[SupportRequestResponse]
)
def read_all_support_requests(
    current_user=Depends(
        require_roles(1, 2, 3, 4)
    )
):

    requests_result = request_collection.find()

    requests = [
        request_helper(request)
        for request in requests_result
    ]

    return requests


# Get one support request by ID
@app.get(
    "/support-requests/{id}",
    response_model=SupportRequestResponse
)
def read_support_request_by_id(
    id: str,
    current_user=Depends(
        require_roles(1, 2, 3, 4)
    )
):

    if not ObjectId.is_valid(id):

        raise HTTPException(
            status_code=400,
            detail="Invalid support request ID format"
        )

    request_result = request_collection.find_one(
        {"_id": ObjectId(id)}
    )

    if not request_result:

        raise HTTPException(
            status_code=404,
            detail="Hospital support request not found"
        )

    return request_helper(request_result)


# Update support request
@app.put(
    "/support-requests/{id}",
    response_model=SupportRequestResponse
)
def update_support_request(
    id: str,
    payload: SupportRequestCreate,
    current_user=Depends(
        require_roles(2, 3, 4)
    )
):

    if not ObjectId.is_valid(id):

        raise HTTPException(
            status_code=400,
            detail="Invalid support request ID format"
        )

    result = request_collection.update_one(
        {"_id": ObjectId(id)},
        {
            "$set": payload.model_dump()
        }
    )

    if result.matched_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Hospital support request not found"
        )

    updated_request = request_collection.find_one(
        {"_id": ObjectId(id)}
    )

    return request_helper(updated_request)


# Delete support request
@app.delete(
    "/support-requests/{id}"
)
def delete_support_request(
    id: str,
    current_user=Depends(
        require_roles(4)
    )
):

    if not ObjectId.is_valid(id):

        raise HTTPException(
            status_code=400,
            detail="Invalid support request ID format"
        )

    result = request_collection.delete_one(
        {"_id": ObjectId(id)}
    )

    if result.deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Hospital support request not found"
        )

    return {
        "message": "Hospital support request deleted successfully"
    }