import json
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from .core import client, WEAK_MODEL

class SemanticEvalSchema(BaseModel):
    matched: bool = Field(description="Whether the condition is matched.")
    confidence: float = Field(description="Confidence from 0.0 to 1.0.")

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True
)
def _nexa_semantic_eval_with_retry(condition: str, target_text: str) -> bool:
    resp = client.chat.completions.create(
        model=WEAK_MODEL,
        messages=[
            {"role": "system", "content": f"Evaluate condition against target text. Condition: {condition} - Respond EXACTLY with a JSON object like {{'matched': bool, 'confidence': float}}."},
            {"role": "user", "content": str(target_text)}
        ],
        response_format={"type": "json_object"},
        timeout=10.0
    )
    content = resp.choices[0].message.content or "{}"
    try:
        data = json.loads(content)
        return bool(data.get("matched", False))
    except Exception:
        return False

def nexa_semantic_eval(condition: str, target_text: str) -> bool:
    print(f"[Semantic_IF Evaluating] Condition: '{condition}'")
    try:
        matched = _nexa_semantic_eval_with_retry(condition, target_text)
        print(f"[Semantic_IF Result] -> {matched}")
        return matched
    except Exception as e:
        print(f"[Nexa Runtime Warning] Semantic eval failed after retries: {e}. Defaulting to False.")
        return False

def nexa_intent_routing(intents: list[str], target_text: str) -> str:
    print(f"[Intent Routing] Matching '{target_text}' against intents: {intents}")
    # Using the weak model to pick an intent
    intents_str = ", ".join([f"'{i}'" for i in intents])
    resp = client.chat.completions.create(
        model=WEAK_MODEL,
        messages=[
            {"role": "system", "content": f"Classify the text into exactly ONE of the following intents: {intents_str}. Respond EXACTLY with a JSON object like {{'intent': '<matched_intent>'}}."},
            {"role": "user", "content": str(target_text)}
        ],
        response_format={"type": "json_object"},
        timeout=10.0
    )
    try:
        data = json.loads(resp.choices[0].message.content or "{}")
        matched_intent = data.get("intent", "")
        if matched_intent in intents:
            print(f"[Intent Match] -> {matched_intent}")
            return matched_intent
    except Exception:
        pass
    print("[Intent Match] -> Fallback to default/None")
    return ""
