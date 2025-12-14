import os
from typing import Dict, List, Optional, Tuple

from src.settings import TEMPLATE_ROOT


DEFAULT_TARGET_MAPPING: Dict[str, str] = {
    "消息输入框": "input_box.png",
    "消息发送按钮": "send_button.png",
}


class TemplateRepository:
    """
    模版仓库，根据分辨率选取最匹配的模版文件。
    新增模版时，将文件放到对应分辨率目录即可，无需改动代码。
    """

    def __init__(
        self,
        template_root: str = TEMPLATE_ROOT,
        target_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        self.template_root = template_root
        self.target_mapping = target_mapping or DEFAULT_TARGET_MAPPING

    def get_template_path(
        self, target: str, resolution: Optional[Tuple[int, int]]
    ) -> Optional[str]:
        filename = self._resolve_filename(target)
        if not filename:
            return None

        folder = self._pick_resolution_folder(resolution)
        if not folder:
            return None

        candidate = os.path.join(self.template_root, folder, filename)
        if os.path.exists(candidate):
            return candidate
        return None

    def _resolve_filename(self, target: str) -> Optional[str]:
        if target in self.target_mapping:
            return self.target_mapping[target]

        normalized = target.strip().replace(" ", "_")
        if not normalized:
            return None
        return f"{normalized}.png"

    def _pick_resolution_folder(
        self, resolution: Optional[Tuple[int, int]]
    ) -> Optional[str]:
        available = self._list_resolution_folders()
        if not available:
            return None
        if not resolution:
            return available[0]

        target_width, target_height = resolution
        best_folder = None
        best_distance = None

        for folder in available:
            parts = folder.split("-")
            if len(parts) != 2:
                continue
            try:
                width = int(parts[0])
                height = int(parts[1])
            except ValueError:
                continue

            distance = abs(width - target_width) + abs(height - target_height)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_folder = folder

        return best_folder

    def _list_resolution_folders(self) -> List[str]:
        if not os.path.exists(self.template_root):
            return []
        folders = []
        for name in os.listdir(self.template_root):
            folder_path = os.path.join(self.template_root, name)
            if os.path.isdir(folder_path):
                folders.append(name)
        return folders
