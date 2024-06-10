import hashlib

from passlib.hash import md5_crypt as md5
from passlib.hash import sha256_crypt as sha256
from passlib.hash import sha512_crypt as sha512

from typing import Any
from pydantic import BaseModel

from rpc import RPCClient, RPCUnauthorized


class IPv4Model(BaseModel):
    gateway: str
    dns: list[str]
    ip: str


class StatusResponse(BaseModel):
    status: int
    ipv4: IPv4Model


class SecondWAN(BaseModel):
    mode: int


class EthernetStatusResponse(StatusResponse):
    protocol: str
    secondwan: SecondWAN
    mode: int


class TetheringDevice(BaseModel):
    device: str
    type: int
    use: bool


class TetheringStatusResponse(StatusResponse):
    devices: list[TetheringDevice]


class NetworkStatus(BaseModel):
    online: bool
    up: bool
    interface: str


class SystemStatusResponse(BaseModel):
    client: Any
    network: list[NetworkStatus]
    service: list[Any]
    system: Any


class ChallengeResponse(BaseModel):
    alg: int
    nonce: str
    salt: str


class LoginResponse(BaseModel):
    sid: str
    username: str


class GlInetClient(RPCClient):
    _algo_map = {
        "1": lambda passwd, salt: md5.hash(passwd, salt=salt),
        "5": lambda passwd, salt: sha256.hash(passwd, salt=salt, rounds=5000),
        "6": lambda passwd, salt: sha512.hash(passwd, salt=salt, rounds=5000)
    }

    def __init__(self, router_ip: str="192.168.8.1", username: str="root"):
        super().__init__(router_ip)
        self.auth_token = None
        self.username = username

    def make_rpc_call(self, func_name: str, *args):
        params = [self.auth_token, *args, func_name, {}]
        return self.make_rpc_request(
            params=params,
            method="call",
        )

    def get_detailed_tethering_status(self) -> TetheringStatusResponse:
        request = self.make_rpc_call("get_status", "tethering")
        response = self.exec_rpc(request, TetheringStatusResponse)
        return response

    def get_detailed_ethernet_status(self) -> EthernetStatusResponse:
        request = self.make_rpc_call("get_status", "cable")
        response = self.exec_rpc(request, EthernetStatusResponse)
        return response

    def get_system_status(self) -> SystemStatusResponse:
        request = self.make_rpc_call("get_status", "system")
        response = self.exec_rpc(request, SystemStatusResponse)
        return response

    @staticmethod
    def get_ethernet_status(system_status: SystemStatusResponse):
        # TODO: doesn't feel quite right
        return next(status for status in system_status.network if status.interface == "wan")

    @staticmethod
    def get_tethering_status(system_status: SystemStatusResponse):
        return next(status for status in system_status.network if status.interface == "tethering")
    
    @staticmethod
    def md5_hash(value: str) -> str:
        return hashlib.md5(value.encode("utf-8")).hexdigest()

    def generate_unix_password_hash(self, alg: int, password: str, salt:str):
        hash_func = self._algo_map.get(f"{alg}", None)
        assert hash_func, "Unknown hashing algorithm"
        return hash_func(password, salt=salt)

    def login(self, password: str):
        challenge_request = self.make_rpc_request(method="challenge", params={"username": self.username})
        challenge_response = self.exec_rpc(challenge_request, ChallengeResponse)

        o = self.generate_unix_password_hash(challenge_response.alg, password, challenge_response.salt)
        hash_result = self.md5_hash(f"{self.username}:{o}:{challenge_response.nonce}")

        login_request = self.make_rpc_request(method="login", params={"username": self.username, "hash": hash_result})
        login_response: LoginResponse = self.exec_rpc(login_request, LoginResponse)

        self.auth_token = login_response.sid
