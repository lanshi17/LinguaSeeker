# app.py--后端启动入口
from fastapi import FastAPI
from src.controller import task_controller

app = FastAPI()
app.include_router(task_controller.router())

# --- IGNORE ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)