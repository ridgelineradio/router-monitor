from typing import Any, Generic, Literal, TypeVar
from pydantic import BaseModel
import requests


T = TypeVar("T")


class RPCRequest(BaseModel, Generic[T]):
    id: int
    params: T
    jsonrpc: Literal["2.0"] = "2.0"
    method: str


class RPCResponse(BaseModel, Generic[T]):
    id: int
    jsonrpc: Literal["2.0"]
    result: T


class ErrorBody(BaseModel):
    message: str
    code: int


class RPCError(BaseModel):
    id: int
    jsonrpc: Literal["2.0"]
    error: ErrorBody


class RPCException(Exception):
    pass


class RPCUnauthorized(RPCException):
    pass


class RPCClient:
    rpc_id = 1

    def __init__(self, router_ip: str):
        self.router_ip = router_ip

    def make_rpc_request(self, **kwargs):
        self.rpc_id += 1
        return RPCRequest(
            id=self.rpc_id,
            **kwargs,
        )

    def exec_rpc(self, rpc_call: RPCRequest, response_model: BaseModel) -> T:
        rpc_request = rpc_call.model_dump()
        response = requests.post(f"http://{self.router_ip}/rpc", json=rpc_request)

        response_data = response.json()

        try:
            response_model = RPCResponse[response_model].model_validate(response_data)
        except Exception as exc:
            response_error = RPCError.model_validate(response_data)
            if response_error.error.message == "Access denied":
                raise RPCUnauthorized()

        return response_model.result
