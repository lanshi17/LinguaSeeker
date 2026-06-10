# Model Server

> Standalone FastAPI microservice providing OpenAI-compatible Embedding, Rerank, and VLM document extraction APIs.
> All inference runs through vllm. Models lazy-load per request and are unloaded after inference so the services can share a single GPU.

(Quick-start instructions updated as part of this migration — see commit history.)
