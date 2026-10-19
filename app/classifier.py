"""학습된 KLUE-RoBERTa로 질문의 의도를 분류한다.

모델 폴더(기본값: outputs/)에는 아래 파일이 있어야 한다.
    config.json, model.safetensors, tokenizer.json, tokenizer_config.json
다른 위치에 있으면 환경변수 MODEL_DIR 로 지정한다.
"""
import os
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = ROOT / "outputs"


class IntentClassifier:
    def __init__(self, model_dir=None, max_length=64):
        model_dir = Path(model_dir or os.getenv("MODEL_DIR") or DEFAULT_MODEL_DIR)
        if not (model_dir / "config.json").exists():
            raise FileNotFoundError(f"모델 폴더를 찾을 수 없어요: {model_dir}")

        # 짧은 문장 1개씩 추론하므로 CPU로도 충분히 빠르다
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(self.device).eval()
        self.id2label = {int(k): v for k, v in self.model.config.id2label.items()}
        self.max_length = max_length

    @torch.no_grad()
    def predict_proba(self, text: str) -> dict:
        """{"의도": 확률} 을 확률 높은 순으로 돌려준다."""
        enc = self.tokenizer(text, truncation=True, max_length=self.max_length,
                             return_tensors="pt").to(self.device)
        probs = torch.softmax(self.model(**enc).logits[0], dim=-1).cpu().tolist()
        pairs = sorted(((self.id2label[i], p) for i, p in enumerate(probs)),
                       key=lambda x: x[1], reverse=True)
        return dict(pairs)
