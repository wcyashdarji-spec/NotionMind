from __future__ import annotations

import torch
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from src.config import logger


class ClipService:
    """
    Service class for openai/clip-vit-base-patch32 text and image embedding.
    """

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32") -> None:
        """
        Load the CLIP model and processor.
        """
        self.model_name = model_name
        try:
            logger.info(f"Loading CLIP model and processor for '{model_name}' ...")
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = CLIPModel.from_pretrained(model_name).to(self.device)
            self.processor = CLIPProcessor.from_pretrained(model_name)
            logger.info(f"CLIP model loaded successfully on device: {self.device}")
        except Exception as exc:
            logger.error(f"Failed to load CLIP model '{model_name}': {exc}")
            raise RuntimeError(f"CLIP model load failed: {exc}") from exc

    def get_text_embedding(self, text: str) -> list[float]:
        """
        Generate a normalized 512-dimension vector embedding for text.
        """
        try:
            inputs = self.processor(
                text=[text], return_tensors="pt", padding=True, truncation=True
            ).to(self.device)
            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)
                
                # Extract tensor if wrapped in BaseModelOutputWithPooling
                if not torch.is_tensor(text_features):
                    if hasattr(text_features, "text_features"):
                        text_features = text_features.text_features
                    elif hasattr(text_features, "pooler_output"):
                        text_features = text_features.pooler_output
                    elif isinstance(text_features, (list, tuple)):
                        text_features = text_features[0]

                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            return text_features.cpu().numpy()[0].tolist()
        except Exception as exc:
            logger.error(f"CLIP get_text_embedding failed for '{text[:40]}': {exc}")
            raise

    def get_image_embedding(self, image: Image.Image) -> list[float]:
        """
        Generate a normalized 512-dimension vector embedding for a PIL Image.
        """
        try:
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                
                # Extract tensor if wrapped in BaseModelOutputWithPooling
                if not torch.is_tensor(image_features):
                    if hasattr(image_features, "image_features"):
                        image_features = image_features.image_features
                    elif hasattr(image_features, "pooler_output"):
                        image_features = image_features.pooler_output
                    elif isinstance(image_features, (list, tuple)):
                        image_features = image_features[0]

                image_features = image_features / image_features.norm(
                    dim=-1, keepdim=True
                )
            return image_features.cpu().numpy()[0].tolist()
        except Exception as exc:
            logger.error(f"CLIP get_image_embedding failed: {exc}")
            raise
