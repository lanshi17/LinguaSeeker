from main import app


if __name__ == "__main__":
    import uvicorn

    from src.config import app_config as cfg

    uvicorn.run(app, host=cfg.host, port=cfg.port, env_file=".env.local")
