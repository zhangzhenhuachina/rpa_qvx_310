import os
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Optional, Tuple

from src.core import system_info
from src.core.screenshot import CAPTURE_LOCK, capture_desktop
from src.core.types import BBox
from src.qvx_position.matcher import OpenCVTemplateMatcher
from src.qvx_position.template_repository import TemplateRepository


@dataclass(frozen=True)
class LocateResult:
    target: str
    resolution: Optional[Tuple[int, int]]
    template_path: Optional[str]
    screenshot_path: Optional[str]
    annotated_screenshot_path: Optional[str]
    score: Optional[float]
    bbox: Optional[BBox]
    reason: Optional[str]

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        bbox = data.get("bbox")
        if bbox is not None:
            data["bbox"] = {"x": bbox["x"], "y": bbox["y"], "width": bbox["width"], "height": bbox["height"]}
        return data


class PositionLocator:
    """根据屏幕截图和模板，返回元素的 BBox。"""

    def __init__(
        self,
        repository: Optional[TemplateRepository] = None,
        matcher: Optional[OpenCVTemplateMatcher] = None,
    ) -> None:
        self.repository = repository or TemplateRepository()
        self.matcher = matcher or OpenCVTemplateMatcher()

    def find_bbox(self, target: str) -> Optional[BBox]:
        result = self.locate(target)
        return result.bbox

    def _annotate_bbox(self, screenshot_path: str, bbox: BBox) -> Optional[str]:
        try:
            from PIL import Image, ImageDraw  # type: ignore
        except Exception:
            return None

        if not os.path.exists(screenshot_path):
            return None

        base, ext = os.path.splitext(screenshot_path)
        annotated_path = f"{base}_bbox{ext or '.png'}"

        try:
            image = Image.open(screenshot_path)
            draw = ImageDraw.Draw(image)
            x1 = int(bbox.x)
            y1 = int(bbox.y)
            x2 = int(bbox.x + bbox.width)
            y2 = int(bbox.y + bbox.height)
            draw.rectangle([x1, y1, x2, y2], outline="red", width=4)
            image.save(annotated_path)
            return annotated_path
        except Exception:
            return None

    def _annotate_bboxes(self, screenshot_path: str, bboxes: Dict[str, BBox], annotated_path: str) -> Optional[str]:
        try:
            from PIL import Image, ImageDraw  # type: ignore
        except Exception:
            return None

        if not os.path.exists(screenshot_path):
            return None

        try:
            image = Image.open(screenshot_path)
            draw = ImageDraw.Draw(image)
            for _target, bbox in bboxes.items():
                x1 = int(bbox.x)
                y1 = int(bbox.y)
                x2 = int(bbox.x + bbox.width)
                y2 = int(bbox.y + bbox.height)
                draw.rectangle([x1, y1, x2, y2], outline="red", width=4)
            image.save(annotated_path)
            return annotated_path
        except Exception:
            return None

    def locate(self, target: str) -> LocateResult:
        resolution = system_info.get_screen_resolution()
        template_path = self.repository.get_template_path(target, resolution)
        if not template_path:
            return LocateResult(
                target=target,
                resolution=resolution,
                template_path=None,
                screenshot_path=None,
                annotated_screenshot_path=None,
                score=None,
                bbox=None,
                reason="template_not_found",
            )

        with CAPTURE_LOCK:
            screenshot_path = capture_desktop()
            if not screenshot_path:
                return LocateResult(
                    target=target,
                    resolution=resolution,
                    template_path=template_path,
                    screenshot_path=None,
                    annotated_screenshot_path=None,
                    score=None,
                    bbox=None,
                    reason="screenshot_failed",
                )

            match_with_score = getattr(self.matcher, "match_with_score", None)
            if callable(match_with_score):
                bbox, score = match_with_score(screenshot_path, template_path)
            else:
                bbox = self.matcher.match(screenshot_path, template_path)
                score = None
            if not bbox:
                return LocateResult(
                    target=target,
                    resolution=resolution,
                    template_path=template_path,
                    screenshot_path=screenshot_path,
                    annotated_screenshot_path=None,
                    score=score,
                    bbox=None,
                    reason="no_match",
                )

        return LocateResult(
            target=target,
            resolution=resolution,
            template_path=template_path,
            screenshot_path=screenshot_path,
            annotated_screenshot_path=None,
            score=score,
            bbox=bbox,
            reason=None,
        )

    def locate_many(
        self,
        targets: Iterable[str],
        *,
        screenshot_path: Optional[str] = None,
        annotated_path: Optional[str] = None,
    ) -> Dict[str, LocateResult]:
        target_list = [t for t in targets if t]
        resolution = system_info.get_screen_resolution()

        results: Dict[str, LocateResult] = {}
        if not target_list:
            return results

        with CAPTURE_LOCK:
            shot_path = capture_desktop(screenshot_path) if screenshot_path else capture_desktop()
            if not shot_path:
                for target in target_list:
                    template_path = self.repository.get_template_path(target, resolution)
                    results[target] = LocateResult(
                        target=target,
                        resolution=resolution,
                        template_path=template_path,
                        screenshot_path=None,
                        annotated_screenshot_path=None,
                        score=None,
                        bbox=None,
                        reason="screenshot_failed",
                    )
                return results

            found_bboxes: Dict[str, BBox] = {}
            for target in target_list:
                template_path = self.repository.get_template_path(target, resolution)
                if not template_path:
                    results[target] = LocateResult(
                        target=target,
                        resolution=resolution,
                        template_path=None,
                        screenshot_path=shot_path,
                        annotated_screenshot_path=None,
                        score=None,
                        bbox=None,
                        reason="template_not_found",
                    )
                    continue

                # 发送按钮容易在可变布局下误匹配到其它位置：只在“右下区域”做匹配。
                if target == "消息发送按钮":
                    bbox, score = self._match_send_button_in_bottom_right(shot_path, template_path)
                else:
                    match_with_score = getattr(self.matcher, "match_with_score", None)
                    if callable(match_with_score):
                        bbox, score = match_with_score(shot_path, template_path)
                    else:
                        bbox = self.matcher.match(shot_path, template_path)
                        score = None

                if not bbox:
                    results[target] = LocateResult(
                        target=target,
                        resolution=resolution,
                        template_path=template_path,
                        screenshot_path=shot_path,
                        annotated_screenshot_path=None,
                        score=score,
                        bbox=None,
                        reason="no_match",
                    )
                    continue

                found_bboxes[target] = bbox
                results[target] = LocateResult(
                    target=target,
                    resolution=resolution,
                    template_path=template_path,
                    screenshot_path=shot_path,
                    annotated_screenshot_path=None,
                    score=score,
                    bbox=bbox,
                    reason=None,
                )

            if annotated_path and found_bboxes:
                annotated = self._annotate_bboxes(shot_path, found_bboxes, annotated_path)
                if annotated:
                    for target in list(results.keys()):
                        existing = results[target]
                        if existing.bbox:
                            results[target] = LocateResult(
                                target=existing.target,
                                resolution=existing.resolution,
                                template_path=existing.template_path,
                                screenshot_path=existing.screenshot_path,
                                annotated_screenshot_path=annotated,
                                score=existing.score,
                                bbox=existing.bbox,
                                reason=existing.reason,
                            )

            if annotated_path and not found_bboxes:
                # 即使没有匹配到任何元素，也生成一张“标注图”（原图副本），便于外部观察最新画面。
                try:
                    from PIL import Image  # type: ignore

                    image = Image.open(shot_path)
                    image.save(annotated_path)
                    for target in list(results.keys()):
                        existing = results[target]
                        results[target] = LocateResult(
                            target=existing.target,
                            resolution=existing.resolution,
                            template_path=existing.template_path,
                            screenshot_path=existing.screenshot_path,
                            annotated_screenshot_path=annotated_path,
                            score=existing.score,
                            bbox=existing.bbox,
                            reason=existing.reason,
                        )
                except Exception:
                    pass

            return results

    def _match_send_button_in_bottom_right(
        self, screenshot_path: str, template_path: str
    ) -> Tuple[Optional[BBox], Optional[float]]:
        """
        发送按钮只在屏幕右下区域搜索，避免误匹配到左侧列表等区域。
        返回的是“整张截图坐标系”的 bbox。
        """
        try:
            cv2 = getattr(self.matcher, "_cv2", None)
            if cv2 is None:
                return self.matcher.match_with_score(screenshot_path, template_path)
            screenshot = cv2.imread(screenshot_path)
            template = cv2.imread(template_path)
            if screenshot is None or template is None:
                return None, None

            h, w = screenshot.shape[:2]
            # 经验 ROI：右半屏 + 底部 40%
            x0 = int(w * 0.5)
            y0 = int(h * 0.6)
            roi = screenshot[y0:h, x0:w]

            result = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            if max_val < getattr(self.matcher, "threshold", 0.5):
                return None, float(max_val)

            th, tw = template.shape[:2]
            return (
                BBox(
                    x=int(x0 + max_loc[0]),
                    y=int(y0 + max_loc[1]),
                    width=int(tw),
                    height=int(th),
                ),
                float(max_val),
            )
        except Exception:
            # 回退到全图匹配
            match_with_score = getattr(self.matcher, "match_with_score", None)
            if callable(match_with_score):
                return match_with_score(screenshot_path, template_path)
            bbox = self.matcher.match(screenshot_path, template_path)
            return bbox, None
