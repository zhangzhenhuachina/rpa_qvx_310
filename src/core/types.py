from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class BBox:
    """矩形框，记录左上角坐标以及宽高。"""

    x: int
    y: int
    width: int
    height: int

    def to_list(self) -> List[int]:
        """转换为列表，便于序列化。"""
        return [self.x, self.y, self.width, self.height]

    def to_tuple(self) -> Tuple[int, int, int, int]:
        return self.x, self.y, self.width, self.height
