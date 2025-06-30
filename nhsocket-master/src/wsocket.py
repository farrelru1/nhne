from __future__ import annotations

import json
import time
from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Callable,
    Optional,
    ParamSpec,
    Type,
    TypeVar,
)

from websockets.sync.client import connect
from websockets.frames import CloseCode

from src.exceptions import LoginFailure

if TYPE_CHECKING:
    from account import NHAccount

# WAJIB DIGANTI SETIAP UPDATE
LIVE_VER = "2.0.4"

PAR = ParamSpec("PAR")
RET = TypeVar("RET")


def ensure_connected(func: Callable[PAR, RET]):
    def decorator(*args: PAR.args, **kwargs: PAR.kwargs) -> RET:
        socket: BaseSocket = args[0]  # type: ignore
        if not socket.connected:
            raise RuntimeError("not logged in!")
        res = func(*args, **kwargs)
        if socket.debug:
            print(res)
        return res

    return decorator


class BaseSocket:
    __WS_CONNECTION__ = "ws://games{server}.kageherostudio.com:{port}/nadsocket"

    def __init__(
        self, account: NHAccount, timeout: float = 2.0, debug: bool = False
    ) -> None:
        self._acount = account
        self.timeout = timeout
        self.ws = connect(
            self.__WS_CONNECTION__.format(server=self._acount.server, port=self.port)
        )
        self.connected: bool = False
        self.data: dict = {}
        self.debug = debug

    @property
    def port(self):
        return f"6{str(self._acount.server).rjust(3, '0')}"

    @property
    def connection_payload(self):
        if not self._acount.token:
            self.close()
            raise ValueError("token must be provided, please ensure to log in")
        return json.dumps(
            {
                "type": 8,
                "source": [
                    self._acount.email.lower(),
                    str(self._acount.server),
                    "LDGameRoom",
                    LIVE_VER,
                    "99108",
                    "UNKNOWN_WIFI_1.0_UNKNOWN",
                    self._acount.token,
                ],
                "timeStamp": int(time.time() * 1000),
            }
        )

    def __enter__(self):
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        if exc_type is None:
            self.close()
        else:
            self.close(CloseCode.INTERNAL_ERROR)

    def connect(self):
        self.ws.send(self.connection_payload)
        while 1:
            try:
                data = json.loads(self.ws.recv(5))
                if not isinstance(data["source"], dict):
                    continue
                if self.debug:
                    print(data)
                for attr in data["source"].keys():
                    if attr not in self.data:
                        self.data.update(data["source"])
                        continue
                    if isinstance(self.data[attr], dict):
                        self.data[attr].update(data["source"][attr])
                        continue
                    for src in data["source"][attr]:
                        self.data[attr].append(src)
                        # print(attr)
                if "activities" in data["source"]:
                    break
            except TimeoutError as exc:
                self.close(reason="Timed Out!")
                raise LoginFailure("Failed to log in due to time out!") from exc
        self.connected = True
        self.ws.send(
            json.dumps(
                {
                    "type": 29,
                    "cName": "com.jelly.player.DefaultPlayerEvent",
                    "timeStamp": int(time.time() * 1000),
                }
            )
        )
        self.ws.send(
            json.dumps(
                {
                    "type": 28,
                    "source": {"teamWarst": {}},
                    "timeStamp": int(time.time() * 1000),
                }
            )
        )
        self.ws.send(
            json.dumps(
                {
                    "type": 28,
                    "source": {"enterScene": -1},
                    "timeStamp": int(time.time() * 1000),
                }
            )
        )
        while True:
            try:
                self.ws.recv(1.0)
            except TimeoutError:
                break

    def close(self, code: int = CloseCode.NORMAL_CLOSURE, reason: str = ""):
        self.connected = False
        self.ws.close(code=code, reason=reason)

    def get_recv(self, target_key: str) -> dict | None:
        while 1:
            try:
                data = json.loads(self.ws.recv(self.timeout))
                if target_key not in data["source"]:
                    continue
                return data
            except TimeoutError:
                return None

    @ensure_connected
    def get_cwar_team(self):
        self.ws.send(
            '{"type":28,"source":{"getTeamArmy":{"type":1,"cpage":0}},"timeStamp":1616041871660}'
        )
        return json.loads(self.ws.recv(self.timeout))

    @ensure_connected
    def combine(self, target: str, sources: list[str]):
        combine_url = json.dumps(
            {
                "type": 28,
                "source": {
                    "exchange": {
                        "type": 0,
                        "srcId": "null",
                        "tarId": target,
                        "srcIdx": 0,
                        "tarIdx": 0,
                        "srcList": sources,
                    }
                },
                "timeStamp": int(time.time() * 1000),
            }
        )
        self.ws.send(combine_url)
        return self.get_recv("operResult")

    @ensure_connected
    def fusion(self, target: str, source: str):
        fusion_url = json.dumps(
            {
                "type": 28,
                "source": {
                    "exchange": {
                        "type": 1,
                        "srcId": source,
                        "tarId": target,
                        "srcIdx": 0,
                        "tarIdx": 0,
                        "srcList": [],
                    }
                },
                "timeStamp": int(time.time() * 1000),
            }
        )
        self.ws.send(fusion_url)
        return self.get_recv("operResult")

    @ensure_connected
    def gacha(self, types: int):
        gacha_url = json.dumps(
            {
                "type": 28,
                "source": {"raffle": {"idx": types}},
                "timeStamp": int(time.time() * 1000),
            }
        )
        self.ws.send(gacha_url)
        return self.get_recv("operResult")

    @ensure_connected
    def snt(self):
        self.ws.send(
            json.dumps(
                {
                    "type": 28,
                    "source": {"examFight": 1},
                    "timeStamp": int(time.time() * 1000),
                }
            )
        )
        return self.get_recv("fightRes")

    @ensure_connected
    def gst(self):
        self.ws.send(
            json.dumps(
                {
                    "type": 28,
                    "source": {"newExamFight": 1},
                    "timeStamp": int(time.time() * 1000),
                }
            )
        )
        return self.get_recv("fightRes")

    @ensure_connected
    def dig(self):
        self.ws.send(
            json.dumps(
                {"type": 28, "source": {"dig": 1}, "timeStamp": int(time.time() * 1000)}
            )
        )
        return self.ws.recv()
