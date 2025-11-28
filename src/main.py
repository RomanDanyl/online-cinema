from fastapi import FastAPI

app = FastAPI(title="Online Cinema API")


@app.get("/ping")
def ping():
    return {"message": "pong"}