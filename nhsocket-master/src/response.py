from typing import Generic, TypeVar, TypedDict

from src.models import Ninja

T = TypeVar("T")


class RECV(TypedDict, Generic[T]):
    eventContext: str | None
    type: int
    source: T
    timeStamp: int
    cName: str | None


class HerosResp(TypedDict):
    hes: dict[str, Ninja | None]


class GachaResp(TypedDict):
    player: dict[str, int]
    heros: HerosResp
    operResult: dict[str, int]


class FusionResp(TypedDict):
    heros: HerosResp
    operResult: dict[str, int]
