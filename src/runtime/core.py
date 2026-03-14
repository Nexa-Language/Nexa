from openai import OpenAI
import os

client = OpenAI(
    base_url="https://aihub.arcsysu.cn/v1",
    api_key="sk-lDc9yRMvfPzpxXKuuXB2LA"
)

STRONG_MODEL = "minimax-m2.5"
WEAK_MODEL = "deepseek-chat"
