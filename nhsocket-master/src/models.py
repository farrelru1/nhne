from dataclasses import dataclass
import json
from typing import Tuple, TypedDict

with open("heroes.json", encoding="utf-8") as file:
    NINJAS: dict[str, dict[str, str]] = json.load(file)


class LoginResp(TypedDict):
    accId: str
    bindingId: str
    servers: list[int]
    sgin: str


SkillT = Tuple[int | None, int | None, int | None, int | None, int | None]


class Equip(TypedDict):
    id: int
    lv: int


class Ninja(TypedDict):
    id: int
    lv: int
    rxp: int
    qlv: int  # stack count
    slv: int  # star count
    pt: int
    props: list
    tmptrainprops: list
    skill: Tuple[SkillT, Tuple[int | None], list, Tuple[int | None]]
    sstar: dict[str, int]
    chakra: Tuple[int, int]
    equip: Tuple[Equip | None, Equip | None, Equip | None, Equip | None]
    hstates: list


class Player(TypedDict):
    name: str
    exp: int
    lv: int
    silver: int
    gold: int


@dataclass
class NinjaModel:
    target: int
    id: int
    name: str
    level: int
    star: int
    point: int
    dupes: int
    skill: Tuple[SkillT, Tuple[int | None], list, Tuple[int | None]]
    equip: Tuple[Equip | None, Equip | None, Equip | None, Equip | None]

    @property
    def has_equipment(self):
        return any(self.equip)

    def __str__(self) -> str:
        return f"(Target: {self.target}, ID: {self.id}, name: {self.name}, level: {self.level}, star: {self.star}, dupes: {self.dupes}, point: {self.point}, has equipment: {self.has_equipment})"
