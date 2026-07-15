"""
SigLIP torso-crop embedding extractor.

get_torso_crop isolates the jersey region (skips head/neck, stops before
shorts, trims side margins to avoid arms/background bleed) — embedding the
full bbox instead washes out the jersey-color signal with legs/shorts/skin.
"""

from __future__ import annotations

import cv2
import numpy as np
import torch
from PIL import Image
from transformers import SiglipVisionModel, SiglipImageProcessor

from .config import TeamAssignerConfig


class SiglipEmbedder:
    def __init__(self, config: TeamAssignerConfig):
        self.config = config
        self.processor = SiglipImageProcessor.from_pretrained(config.siglip_model_name)
        self.model = SiglipVisionModel.from_pretrained(config.siglip_model_name).to(config.device).eval()

    def get_torso_crop(self, frame: np.ndarray, bbox: list[float]) -> np.ndarray | None:
        """Returns None if the resulting crop is empty or the bbox is too small."""
        cfg = self.config
        x1, y1, x2, y2 = bbox
        h_img, w_img = frame.shape[:2]

        box_w, box_h = (x2 - x1), (y2 - y1)
        if box_w <= 0 or box_h <= 0 or (box_w * box_h) < cfg.min_bbox_area:
            return None

        top = y1 + cfg.torso_top_ratio * box_h
        bottom = y1 + cfg.torso_bottom_ratio * box_h
        left = x1 + cfg.torso_side_margin * box_w
        right = x2 - cfg.torso_side_margin * box_w

        x1c, y1c, x2c, y2c = int(round(left)), int(round(top)), int(round(right)), int(round(bottom))
        x1c, y1c = max(0, x1c), max(0, y1c)
        x2c, y2c = min(w_img, x2c), min(h_img, y2c)

        if x2c <= x1c or y2c <= y1c:
            return None

        return frame[y1c:y2c, x1c:x2c]

    @torch.no_grad()
    def extract(self, frame_bgr: np.ndarray, bbox: list[float]) -> np.ndarray | None:
        torso = self.get_torso_crop(frame_bgr, bbox)
        if torso is None or torso.size == 0:
            return None

        crop_rgb = cv2.cvtColor(torso, cv2.COLOR_BGR2RGB)
        pil_crop = Image.fromarray(crop_rgb)

        inputs = self.processor(images=pil_crop, return_tensors="pt").to(self.config.device)
        outputs = self.model(**inputs)
        emb = outputs.pooler_output.squeeze(0).cpu().numpy()

        norm = np.linalg.norm(emb)
        return emb / norm if norm > 0 else emb
