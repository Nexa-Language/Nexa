from openai import OpenAI
import os

client = OpenAI(
    base_url="https://aihub.arcsysu.cn/v1",
    api_key="sk-lDc9yRMvfPzpxXKuuXB2LA"
)

STRONG_MODEL = "minimax-m2.5"
WEAK_MODEL = "deepseek-chat"


import base64
import mimetypes

def nexa_fallback(primary_fn, backup_fn):
    try:
        return primary_fn()
    except Exception as e:
        print(f"[Fallback Triggered] Primary failed with: {e}")
        return backup_fn()

def nexa_img_loader(filepath):
    try:
        mime_type, _ = mimetypes.guess_type(filepath)
        if mime_type is None:
            mime_type = "image/jpeg"
        with open(filepath, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{encoded}"}
        }
    except Exception as e:
        print(f"[Image Load Error]: {e}")
        return str(filepath)  # fallback to just returning the path if load fails
