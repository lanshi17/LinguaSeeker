from .api_gateway import ApiGatewayRequest, ApiGatewayResult, call_api_gateway
from .base import LiteratureGatewayAdapter
from .registry import (
    DuplicateGatewayProviderError,
    GatewayAdapterRegistry,
    UnknownGatewayProviderError,
)
from .web_gateway import WebGatewayRequest, WebGatewayResult, call_auto_web_gateway

__all__ = [
    "ApiGatewayRequest",
    "ApiGatewayResult",
    "DuplicateGatewayProviderError",
    "GatewayAdapterRegistry",
    "LiteratureGatewayAdapter",
    "UnknownGatewayProviderError",
    "WebGatewayRequest",
    "WebGatewayResult",
    "call_api_gateway",
    "call_auto_web_gateway",
]
