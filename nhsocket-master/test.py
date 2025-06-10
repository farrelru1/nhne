from os import getenv
from typing import TypedDict


from dotenv import load_dotenv
from src.account import NHAccount, NHNAuth

LIVE_VER = "1.5.4"
load_dotenv()

tcaptured = TypedDict("tcaptured", {"target": str, "sources": list[str]})
captured: dict[int, tcaptured] = {
    15: {"sources": ["1", "2", "3"], "target": "999"},
    16: {"sources": ["52", "223", "123"], "target": "3214"},
}


def main():
    for x in range(1, 21):
        reg = NHNAuth(f"straze{x}@gmail.com", f"straze{x}")
        print(reg)


if __name__ == "__main__":
    main()
