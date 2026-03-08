import sqlite3
from fastapi import APIRouter
from pydantic import BaseModel
from passlib.context import CryptContext

router = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class LoginData(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(data: LoginData):

    conn = sqlite3.connect("ngo.db")
    cur = conn.cursor()

    cur.execute(
        "SELECT password, role FROM users WHERE username=?",
        (data.username,)
    )

    user = cur.fetchone()

    conn.close()

    if user and pwd_context.verify(data.password, user[0]):
        return {"status": "success", "role": user[1]}

    return {"status": "error", "message": "Invalid username or password"}