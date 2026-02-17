import os
import base64

from dotenv import load_dotenv
from openai import OpenAI


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# Load repo-root .env if present
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
load_dotenv(os.path.join(repo_root, ".env"))

model = os.getenv("MODEL_PROVA") or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
image_path = os.getenv("PROVA_IMAGE_PATH", "").strip()

print("[PROVA]")
print("model:", model)
print("image_path:", image_path or "(none)")

client = OpenAI()

content = [{"type": "text", "text": "Ciao, rispondi con un Hello World"}]
if image_path and os.path.exists(image_path):
    img_b64 = _encode_image(image_path)
    content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})

resp = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": content}],
    max_tokens=200,
    temperature=0.0,
)

print(resp.choices[0].message.content or "")
