from fastapi import FastAPI
app=FastAPI()
@app.get("/")
def home():
    return {"Message" : "Enterprise IT Service Desk"}
