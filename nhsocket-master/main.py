import argparse
import getpass
from pathlib import Path
from typing import Any, Callable

from dotenv import load_dotenv
from colorama import Fore

from src.account import NHAccount

load_dotenv()
ACCOUNT_PATH = Path("saved.txt")
if not ACCOUNT_PATH.exists():
    ACCOUNT_PATH.touch()

parser = argparse.ArgumentParser("NHNE terminal tools")
parser.add_argument(
    "--private",
    default=False,
    action="store_true",
    help="Set agar email dan informasi akun terprivasi",
)


def search_from_response(data: dict, search: str) -> tuple[str, Any] | None:
    for key, val in data.items():
        if key == search:
            return (key, val)
        if isinstance(val, dict):
            result = search_from_response(val, search)
        if result:
            return result
    return None


def burn_prompt(acc: NHAccount):
    print("current lineup", acc.lineup)
    amount = input("Amount to burn: ")
    tar_id = input("Target ninja: ")
    by = input("Burn by ['silver', 'capture']: ")
    if by not in ["silver", "capture"]:
        raise ValueError("burn type must be silver or capture")
    target = acc.raw_ninja[tar_id]
    acc.burn_silver(int(amount), tar_id, by)  # type: ignore
    new_target = acc.raw_ninja[tar_id]
    del target


def snt(acc: NHAccount):
    tries = int(input("max percobaan: "))
    acc.ninja_exam(tries)


def gst(acc: NHAccount):
    tries = int(input("max percobaan: "))
    acc.ninja_exam(tries, gst=True)


def gacha(acc: NHAccount):
    amount = int(input("gacha amount: "))
    for _ in range(amount):
        acc.gacha("basic")


def ninjas(acc: NHAccount):
    for ninja in acc.all_ninjas:
        print(ninja)


def fast_combine(acc: NHAccount):
    print(
        f"{Fore.RED}isi gear pada ninja jika tidak ingin terkena combine!{Fore.WHITE}"
    )
    max_level = int(input("Max level untuk skip auto combine: "))
    max_id = int(input("Max ninja ID untuk diskip (cek json): "))
    target = input(
        f"Target ninja untuk dikasih makan (Line Up saat ini: {acc.lineup}): "
    )
    acc.fast_combine(target, max_id, max_level)
    print("Fast combine berhasil!")


def main():
    parsed = parser.parse_args()
    server = int(input("Server: "))
    if not parsed.private:
        user = input("Email: ")
    else:
        user = getpass.getpass("Email: ")
    passwd = getpass.getpass("Password: ")
    menus: dict[str, Callable[[NHAccount], None] | None] = {
        "burn": burn_prompt,
        "snt": snt,
        "gst": gst,
        "gacha": gacha,
        "ninjas": ninjas,
        "combine cepat": fast_combine,
    }
    menus.update({"Keluar": None})
    with NHAccount(
        user,
        passwd,
        server=server,
        privacy=parsed.private,
    ) as game:
        while 1:
            print("=" * 10)
            for idx, menu in enumerate(menus, start=1):
                print(f"{idx}. {menu}")
            choosed = int(input("Pilih menu: "))
            if choosed < 1 or choosed > len(menus):
                print("Salah input")
                continue
            parse_choosed = list(menus)[choosed - 1]
            if menus[parse_choosed] is None:
                break
            menus[parse_choosed](game)
            print(game)


if __name__ == "__main__":
    main()
