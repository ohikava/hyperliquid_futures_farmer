from typing_extensions import TypedDict
from typing import List

class Cloid:
    def __init__(self, raw_cloid: str):
        self._raw_cloid: str = raw_cloid
        self._validate()

    def _validate(self):
        assert self._raw_cloid[:2] == "0x", "cloid is not a hex string"
        assert len(self._raw_cloid[2:]) == 32, "cloid is not 16 bytes"

    @staticmethod
    def from_int(cloid: int):
        return Cloid(f"{cloid:#034x}")

    @staticmethod
    def from_str(cloid: str):
        return Cloid(cloid)

    def to_raw(self):
        return self._raw_cloid

AssetInfo = TypedDict("AssetInfo", {"name": str, "szDecimals": int})
Meta = TypedDict("Meta", {"universe": List[AssetInfo]})