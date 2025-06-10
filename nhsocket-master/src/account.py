import hashlib
from io import StringIO
import json
from types import TracebackType
from typing import Literal, TypedDict
import httpx
from src.response import RECV, FusionResp, GachaResp
from src.wsocket import BaseSocket
from src.exceptions import (
    FusionError,
    FusionLimitError,
    NinjaNotFoundError,
    RunError,
    UnsafeNinjaError,
)
from src.models import Ninja, LoginResp, NinjaModel, Player

with open("heroes.json", encoding="utf-8") as file:
    NINJAS: dict[str, dict[str, str]] = json.load(file)

MAX_NINJA = 200


class NHNAuth:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.secret = "S5#da3331c4fa!38da9bf"

    def __str__(self) -> str:
        return f"Email: {self.email}, passwd: {self.password}"

    def __gen_password__(self):
        return hashlib.md5(
            (self.email + self.password + self.secret).encode()
        ).hexdigest()

    def login(self):
        req = httpx.get(
            f"http://central.kageherostudio.com/game/lyto/login?accId={self.email}&pwd={self.password}&channel=99108&lv=1"
        )
        return req.json()

    def register(self):
        req = httpx.get(
            f"http://central.kageherostudio.com/game/lyto/register?accId={self.email}&pwd={self.password}&channel=99108&sign={self.__gen_password__()}"
        )
        return req.json()


class NHAccount:
    def __init__(
        self,
        email: str,
        password: str,
        server: int = 1,
        privacy: bool = False,
        debug: bool = False,
    ) -> None:
        self.email = email
        self.password = password
        self.server = server
        self.private = privacy
        self.token: str | None = None

        self.socket = BaseSocket(self, debug=debug)

    @property
    def data(self):
        return self.socket.data

    @property
    def player(self) -> Player:
        return self.data["player"]

    @property
    def deploy(self) -> list[int]:
        return self.data["heros"]["aids"]

    @property
    def lineup(self) -> list[int]:
        return self.data["heros"]["mars"]

    @property
    def raw_ninja(self) -> dict[str, Ninja]:
        return self.data["hes"]

    @property
    def ninjas_tar_id(self) -> list[str]:
        return list(self.raw_ninja.keys())

    @property
    def ninjas_id(self) -> list[int]:
        return [val["id"] for val in self.raw_ninja.values()]

    @property
    def all_ninjas(self):

        return [
            NinjaModel(
                target=target,
                id=ninja["id"],
                name=NINJAS.get(str(ninja["id"]), {"nama": "Unknown!"})["nama"],
                level=ninja["lv"],
                star=ninja.get("slv", 0),
                dupes=ninja.get("qlv", 0),
                skill=ninja["skill"],
                equip=ninja["equip"],
                point=ninja["pt"],
            )
            for target, ninja in self.raw_ninja.items()
        ]

    def __str__(self):
        with StringIO() as info:
            info.write(f"Logged in as: {'Logged privately' if self.private else ''}\n")
            if not self.private:
                info.write(f"Village Name: {self.player['name']}\n")
                info.write(f"Village Level: {self.player['lv']}\n")
                info.write(f"Village EXP: {self.player['exp']}\n")
            info.write(f"Silver: {self.player['silver']}\n")
            info.write(f"Gold: {self.player['gold']}\n")
            info.write(f"Total Ninjas: {len(self.ninjas_tar_id)}\n")
            return info.getvalue()

    def __enter__(self):
        self.login()
        self.socket.connect()
        print(str(self))
        return self

    def __exit__(
        self,
        exc_type: BaseException | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.socket.close()
        else:
            self.socket.close(reason="terminated")

    def get_raw_ninja(self, tar_id: str):
        if tar_id not in self.raw_ninja:
            return None
        return self.raw_ninja[tar_id]

    def get_all_ninja_by_id(self, ids: int):
        for key, values in self.raw_ninja.items():
            if values["id"] == ids:
                yield {key: values}

    def safe_ninja(
        self,
        ninja: Ninja,
        max_lv: int = 1,
        ignore: None | Literal["equip", "level", "skill"] = None,
    ):
        """function to ensure ninja is not having skill, equipment
        and level is `lower equal` than `max_lv`

        Args:
            ninja (Ninja): Ninja to check

            max_lv (int): max level to check, default 1

            ignore (Literal["equip", "level", "skill"]):
            which value to ignore check, None will check all
        """
        checks: dict[str, bool] = {
            "equip": not any(ninja["equip"]),
            "level": ninja["lv"] <= max_lv,
            "skill": not any(ninja["skill"][0]),
        }
        if ignore:
            checks.pop(ignore)
        return all(checks.values())

    def get_all_ninja(self, with_lineup: bool = False):
        """Function to get all ninja with or without lineup

        Yields:
            tuple[int, int]: yields ninja TAR_ID and ninja ID

        """
        for tar_id, ninja_id in zip(self.ninjas_tar_id, self.ninjas_id):
            if not with_lineup and int(tar_id) in self.lineup:
                continue
            yield int(tar_id), ninja_id

    def combine(self, target: str, source: set[str], max_level: int = 1):
        for key in source.copy():
            if key not in self.raw_ninja:
                print(key, "is not found on current ninja!")
                source.remove(key)
                continue
            raw = self.raw_ninja[key]
            if self.safe_ninja(raw, ignore="skill", max_lv=max_level):
                continue

            print("===\nSkipped ninja:", raw["id"])
            print("Level:", raw["lv"])
            print("Equipment:", raw["equip"], "\n===")
            source.remove(key)
        if not source:
            raise NinjaNotFoundError("no ninja source to combine!")
        recv: RECV[FusionResp] = self.socket.combine(target, list(source))
        if not recv:
            raise RunError("Failed to combine!")
        if "heros" in recv["source"]:
            for key, val in recv["source"]["heros"]["hes"].items():
                if not val:
                    self.raw_ninja.pop(key)
                    continue
                self.raw_ninja.update({key: val})
        return recv

    def fast_combine(self, target: str, max_id: int, max_level: int = 1):
        """function to combine all ninja
        with every ninja that has `id < max_id` will be combined

        Args:
            target (str): ninja `TAR ID` target
            max_id (int): minimum ninja `ID` to be combined to target
            max_level (int): max level ninja to be combined to target
        """
        sources = set(
            str(tar_ids) for tar_ids, ids in self.get_all_ninja() if ids < max_id
        )
        if not sources:
            return "no ninja source to combine!"
        return self.combine(target, sources, max_level)

    def fusion(self, target: str, source: str):
        if target not in self.raw_ninja or source not in self.raw_ninja:
            raise NinjaNotFoundError("ninja target or source not found")
        src_ninja = self.raw_ninja[source]
        tar_ninja = self.raw_ninja[target]
        if "qlv" in tar_ninja and tar_ninja["qlv"] >= 10:
            raise FusionLimitError("Target ninja is already maxed!")
        if not self.safe_ninja(src_ninja, ignore="skill"):
            raise UnsafeNinjaError("ninja source is having equipment")
        if src_ninja["id"] != tar_ninja["id"]:
            raise FusionError("ninja ID must be same!")
        recv: RECV[FusionResp] = self.socket.fusion(target=target, source=source)
        if not recv:
            raise RunError("failed to perform fusion!")
        if "heros" in recv["source"]:
            for key, val in recv["source"]["heros"]["hes"].items():
                if not val:
                    self.raw_ninja.pop(key)
                    continue
                self.raw_ninja.update({key: val})
        return recv

    def fast_fusion(self, target: str):
        tar_ninja = self.get_raw_ninja(target)
        if not tar_ninja:
            raise NinjaNotFoundError("target ninja not found!")
        sources = [
            str(tar)
            for tar, ids in self.get_all_ninja()
            if ids == tar_ninja["id"] and tar != int(target)
        ]
        for source in sources:
            try:
                self.fusion(target, source)
            except (
                RunError,
                FusionLimitError,
                NinjaNotFoundError,
                UnsafeNinjaError,
            ) as exc:
                print("fast fusion terminated: ", exc)
                break

    def gacha(self, types: Literal["basic", "advanced", "special"]):
        type_maps = {
            "basic": 0,
            "advanced": 1,
            "special": 2,
        }
        if types not in type_maps:
            raise ValueError(f"cannot find {types} type")
        recv: RECV[GachaResp] = self.socket.gacha(type_maps[types])
        if not recv:
            raise RunError("failed to get ninja!")
        source = recv["source"]
        ninja_id: int = source["operResult"]["param"]
        if "heros" in source and "hes" in source["heros"]:
            self.raw_ninja.update(source["heros"]["hes"])  # type: ignore
        ninja_name = NINJAS.get(str(ninja_id), {"nama": "Unknown"})
        print("Captured", ninja_name["nama"])
        return recv

    def ninja_exam(self, max_tries: int = 5, gst: bool = False):
        while max_tries:
            if gst:
                recv = self.socket.gst()
            else:
                recv = self.socket.snt()
            if not recv:
                break
            is_winning = recv["source"]["fightRes"]["win"]
            if not bool(is_winning):
                max_tries -= 1
            print("Win status:", bool(is_winning))
        print("Done performing ninja exam")

    def _burn_combine(self, target: str, captured: dict):
        rest_ninja: list[str] = []
        for caps in captured.values():
            while caps["sources"]:
                try:
                    self.fusion(caps["target"], caps["sources"].pop())
                except FusionLimitError:
                    rest_ninja.extend(caps["sources"])
                    break
            fusioned = self.raw_ninja[caps["target"]]
            print(
                (
                    f"fusioned ninja: (ID: {fusioned['id']}, "
                    + f"Dupes: +{fusioned.get('qlv', 0)}, "
                    + f"Star: {fusioned.get('slv', 0)})"
                )
            )
        self.combine(target, set(caps["target"] for caps in captured.values()))
        if rest_ninja:
            self.combine(target, set(rest_ninja))

    def burn_silver(
        self, amount: int, target: str, by: Literal["silver", "capture"] = "capture"
    ):
        """function to perform burn silver

        Args:
            amount (int): amount to burn
            target (str): target TAR_ID ninja to combine the burned ninja
            by Literal["silver", "capture"]:
            choose which to burn by, silver or capture time. Defaults to "capture".

        Raises:
            ValueError: not enough silver to burn
        """
        if target not in self.raw_ninja:
            raise ValueError("current target is not on ninja list!")
        if amount < 30000 and by == "silver":
            raise ValueError("minimum silver to burn is 30000")
        silver = self.player["silver"]
        remaining = (silver - amount) if by == "silver" else (silver - 30000 * amount)
        if remaining <= 30000:
            raise ValueError("not enough silver to burn")
        print("Total silver after burn:", remaining)
        capture_count = amount if by == "capture" else amount // 30000
        gacha_count = MAX_NINJA - len(self.raw_ninja) - 1
        for num in range(0, capture_count, gacha_count):
            tcaptured = TypedDict("tcaptured", {"target": str, "sources": list[str]})
            captured: dict[int, tcaptured] = {}
            for x in range(num, num + gacha_count):
                if x > capture_count:
                    break
                try:
                    gacha_res = self.gacha("basic")
                except RunError:
                    print("failed to pull a ninja")
                    continue
                if "heros" not in gacha_res["source"]:
                    continue
                tar_id: str = list(gacha_res["source"]["heros"]["hes"].keys())[0]
                ninja: Ninja = gacha_res["source"]["heros"]["hes"][tar_id]
                if ninja["id"] not in captured:
                    captured[ninja["id"]] = {"target": tar_id, "sources": []}
                    continue
                captured[ninja["id"]]["sources"].append(tar_id)
            self._burn_combine(target, captured)

    def login(self) -> LoginResp:
        req = httpx.get(
            "http://central.kageherostudio.com/game/lyto/login?channel=99108&lv=1",
            params={"accId": self.email, "pwd": self.password},
        )
        data = req.json()
        if data["code"] != 1:
            self.socket.close()
            raise RunError("failed to log in!")
        json_data: LoginResp = json.loads(data["msg"])
        self.token = json_data["sgin"]
        return json_data
