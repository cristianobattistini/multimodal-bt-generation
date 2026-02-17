import base64
import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import logging

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    NotFoundError,
    OpenAI,
    RateLimitError,
)


@dataclass
class OpenAIConfig:
    api_key: str
    default_model: Optional[str]
    service_tier: Optional[str]
    reasoning_effort: Optional[str]
    default_max_tokens: int
    timeout_s: float
    max_retries: int
    retry_base_sleep: float
    retry_max_sleep: Optional[float]
    allow_model_fallback: bool


def load_openai_config() -> OpenAIConfig:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY (set it in environment or .env).")

    default_model = os.getenv("OPENAI_MODEL", "").strip() or "gpt-5-mini"

    service_tier = os.getenv("OPENAI_SERVICE_TIER", "").strip() or None

    reasoning_effort_raw = os.getenv("OPENAI_REASONING_EFFORT", "low").strip().lower()
    reasoning_effort = None
    if reasoning_effort_raw and reasoning_effort_raw not in {"0", "false", "no", "none", "off"}:
        if reasoning_effort_raw not in {"low", "medium", "high"}:
            raise ValueError(
                "Invalid OPENAI_REASONING_EFFORT. Expected one of: low, medium, high (or empty to disable)."
            )
        reasoning_effort = reasoning_effort_raw

    default_max_tokens = 1600
    max_tokens_raw = (
        os.getenv("OPENAI_MAX_COMPLETION_TOKENS", "").strip()
        or os.getenv("OPENAI_MAX_TOKENS", "").strip()
        or os.getenv("OPENAI_DEFAULT_MAX_TOKENS", "").strip()
    )
    if max_tokens_raw:
        try:
            default_max_tokens = max(1, int(max_tokens_raw))
        except ValueError:
            default_max_tokens = 1600

    timeout_s = 900.0
    try:
        timeout_s = float(os.getenv("OPENAI_TIMEOUT", "900").strip() or "900")
    except ValueError:
        timeout_s = 900.0
    try:
        max_retries = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
    except ValueError:
        max_retries = 2

    try:
        retry_base_sleep = float(os.getenv("OPENAI_RETRY_BASE_SLEEP", "1.5"))
    except ValueError:
        retry_base_sleep = 1.5

    retry_max_sleep = 15.0
    try:
        retry_max_sleep_raw = os.getenv("OPENAI_RETRY_MAX_SLEEP")
    except Exception:
        retry_max_sleep_raw = None
    if retry_max_sleep_raw is not None and retry_max_sleep_raw.strip() != "":
        try:
            retry_max_sleep = float(retry_max_sleep_raw.strip())
        except ValueError:
            retry_max_sleep = 15.0

    # Default: do NOT silently fall back to a different model when a model name is wrong.
    allow_fallback_raw = os.getenv("OPENAI_ALLOW_MODEL_FALLBACK", "0").strip().lower()
    allow_model_fallback = allow_fallback_raw not in {"0", "false", "no"}

    return OpenAIConfig(
        api_key=api_key,
        default_model=default_model,
        service_tier=service_tier,
        reasoning_effort=reasoning_effort,
        default_max_tokens=default_max_tokens,
        timeout_s=max(1.0, float(timeout_s)),
        max_retries=max(0, max_retries),
        retry_base_sleep=max(0.1, retry_base_sleep),
        retry_max_sleep=None if retry_max_sleep is None else max(0.1, float(retry_max_sleep)),
        allow_model_fallback=allow_model_fallback,
    )


class LLMClient:
    def __init__(self, *, model: Optional[str] = None) -> None:
        cfg = load_openai_config()
        self.default_model = model or cfg.default_model
        if not self.default_model:
            raise ValueError("OpenAI model name is required.")
        self.service_tier = cfg.service_tier
        self.reasoning_effort = cfg.reasoning_effort
        self.default_max_tokens = cfg.default_max_tokens
        self.max_retries = cfg.max_retries
        self.retry_base_sleep = cfg.retry_base_sleep
        self.retry_max_sleep = cfg.retry_max_sleep
        self.allow_model_fallback = cfg.allow_model_fallback
        # We implement our own retry loop to keep sleep bounded; disable SDK retries.
        self.client = OpenAI(api_key=cfg.api_key, max_retries=0, timeout=cfg.timeout_s)

    def _guess_mime(self, image_path: str) -> str:
        ext = os.path.splitext(image_path)[1].lower()
        if ext in {".png"}:
            return "image/png"
        return "image/jpeg"

    def _encode_image(self, image_path: str, *, mode: Optional[str] = None) -> tuple[str, str]:
        """
        Returns (mime, b64).
        mode:
          - None / "rgb": raw bytes passthrough
          - "grayscale": decode -> grayscale -> re-encode as jpeg
        """
        mode = (mode or "").strip().lower() or "rgb"
        if mode == "grayscale":
            try:
                import cv2  # type: ignore

                img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
                if img is None:
                    raise ValueError("cv2.imread returned None")
                ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if not ok:
                    raise ValueError("cv2.imencode failed")
                b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
                return "image/jpeg", b64
            except Exception:
                # Fallback: send original bytes.
                pass

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return self._guess_mime(image_path), b64

    def complete(
        self,
        prompt: str,
        *,
        image_path: Optional[str] = None,
        image_mode: Optional[str] = None,
        system: Optional[str] = None,
        model: Optional[str] = None,
        service_tier: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        messages: List[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})

        if image_path:
            mime, img_b64 = self._encode_image(image_path, mode=image_mode)
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{img_b64}"},
                },
            ]
        else:
            content = prompt

        messages.append({"role": "user", "content": content})

        target_model = model or self.default_model
        resolved_max_tokens = self.default_max_tokens if max_tokens is None else max(1, int(max_tokens))

        # GPT-5 and o-series models do not support temperature.
        # They also require `max_completion_tokens` instead of `max_tokens`.
        is_reasoning_model = target_model.startswith(("gpt-5", "o"))

        kwargs = {"model": target_model, "messages": messages}
        if is_reasoning_model:
            kwargs["max_completion_tokens"] = resolved_max_tokens
        else:
            kwargs["max_tokens"] = resolved_max_tokens

        resolved_service_tier = (service_tier or self.service_tier or "").strip() or None
        if resolved_service_tier is not None:
            kwargs["service_tier"] = resolved_service_tier
        if is_reasoning_model:
            if self.reasoning_effort is not None:
                kwargs["reasoning_effort"] = self.reasoning_effort
        else:
            kwargs["temperature"] = temperature

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""
        if not content.strip():
            logging.warning(
                "LLM returned empty content (model=%s finish_reason=%s usage=%s).",
                target_model,
                getattr(choice, "finish_reason", None),
                getattr(response, "usage", None),
            )
        return content

    def _parse_retry_after(self, exc: Exception) -> Optional[float]:
        resp = getattr(exc, "response", None)
        if resp is None:
            return None
        headers = getattr(resp, "headers", None)
        if not headers:
            return None
        raw = headers.get("retry-after")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _sleep_with_backoff(self, attempt: int, *, retry_after: Optional[float]) -> float:
        base = self.retry_base_sleep * (2 ** attempt)
        sleep_s = base
        if retry_after is not None:
            sleep_s = max(base, retry_after)
        if self.retry_max_sleep is not None:
            sleep_s = min(self.retry_max_sleep, sleep_s)
        jitter = random.uniform(0.0, min(0.5, sleep_s * 0.1))
        sleep_s = max(0.1, sleep_s + jitter)
        time.sleep(sleep_s)
        return sleep_s

    def _complete_with_retry(
        self,
        *,
        prompt: str,
        image_path: Optional[str],
        image_mode: Optional[str],
        system: Optional[str],
        model: Optional[str],
        temperature: float,
        max_tokens: Optional[int],
    ) -> str:
        if self.retry_max_sleep is None:
            return self.complete(
                prompt,
                image_path=image_path,
                image_mode=image_mode,
                system=system,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        for attempt in range(self.max_retries + 1):
            try:
                return self.complete(
                    prompt,
                    image_path=image_path,
                    image_mode=image_mode,
                    system=system,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except BadRequestError:
                # 400s (e.g., unsupported params) are not transient; do not retry.
                raise
            except (RateLimitError, APITimeoutError, APIConnectionError, APIError) as exc:
                if attempt >= self.max_retries:
                    raise
                retry_after = self._parse_retry_after(exc)
                sleep_s = self._sleep_with_backoff(attempt, retry_after=retry_after)
                logging.warning(
                    "LLM retry after error %s; sleeping %.2fs (attempt %d/%d).",
                    type(exc).__name__,
                    sleep_s,
                    attempt + 1,
                    self.max_retries,
                )
        raise RuntimeError("Unreachable retry loop exit.")

    def complete_with_fallback(
        self,
        prompt: str,
        *,
        image_path: Optional[str] = None,
        image_mode: Optional[str] = None,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Same as `complete`, but if the explicit model is not found and fallback is enabled,
        retries with the client's default model.
        """
        resolved_model = model
        resolved_default = self.default_model
        try:
            return self._complete_with_retry(
                prompt=prompt,
                image_path=image_path,
                image_mode=image_mode,
                system=system,
                model=resolved_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except NotFoundError as exc:
            if resolved_model and resolved_model != resolved_default:
                if not self.allow_model_fallback:
                    raise ValueError(
                        f"OpenAI model not found: '{resolved_model}'. "
                        "Fix by setting the right MODEL_* / OPENAI_MODEL value. "
                        "If you really want fallback, set OPENAI_ALLOW_MODEL_FALLBACK=1."
                    ) from exc
                logging.warning(
                    "OpenAI model '%s' not found; retrying with default '%s'",
                    resolved_model,
                    resolved_default,
                )
                return self._complete_with_retry(
                    prompt=prompt,
                    image_path=image_path,
                    image_mode=image_mode,
                    system=system,
                    model=resolved_default,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            raise
