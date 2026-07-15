"""
OSNet ReID model loader. BoT-SORT uses this internally (via model_weights
path) for its own embeddings; this wrapper exposes the same fine-tuned
weights loaded standalone, matching the exact load procedure from the
notebook (handles both {"state_dict": ...} and raw state-dict checkpoints).
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torchreid
import torchvision.transforms as T


def load_osnet(weights_path: str, device: str):
    """Load the fine-tuned OSNet backbone with its classifier head stripped
    (Identity), ready to produce 512-dim embeddings."""
    ckpt = torch.load(weights_path, map_location="cpu")
    state_dict = ckpt.get("state_dict", ckpt.get("model", ckpt)) if isinstance(ckpt, dict) else ckpt

    model = torchreid.models.build_model(name="osnet_x1_0", num_classes=302, pretrained=False)
    model.load_state_dict(state_dict, strict=True)
    model.classifier = nn.Identity()
    model.eval()
    model.to(device)
    return model


def build_osnet_transform() -> T.Compose:
    return T.Compose([
        T.Resize((256, 128)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
