"""
Unified OpenAI-compatible LLM client for baseline experiments.

Run connection test:

    python rag/llm_client.py --test

Run a custom prompt:

    python rag/llm_client.py --prompt "请简单介绍基底细胞癌。"
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import APIConnectionError
from openai import APIStatusError
from openai import APITimeoutError
from openai import AuthenticationError
from openai import BadRequestError
from openai import OpenAI
from openai import RateLimitError


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"

DEFAULT_CONFIG_FILE = (
    PROJECT_ROOT
    / "configs"
    / "llm_config.yaml"
)


class LLMClientError(RuntimeError):
    """统一模型客户端异常。"""


@dataclass(frozen=True)
class LLMSettings:
    """模型服务及生成参数。"""

    api_key: str
    base_url: str
    model: str

    timeout_seconds: float
    max_retries: int

    temperature: float
    max_completion_tokens: int
    stream: bool
    enable_thinking: bool
    seed: int

    provider: str
    prompt_version: str


@dataclass(frozen=True)
class LLMResult:
    """单次模型调用结果。"""

    content: str

    model: str
    provider: str
    prompt_version: str

    finish_reason: str
    request_id: str

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    latency_seconds: float

    temperature: float
    max_completion_tokens: int
    enable_thinking: bool
    seed: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_scalar(value: str) -> Any:
    """解析当前配置文件使用的简单 YAML 标量。"""

    cleaned = value.strip()

    if not cleaned:
        return ""

    lowered = cleaned.lower()

    if lowered == "true":
        return True

    if lowered == "false":
        return False

    if (
        len(cleaned) >= 2
        and cleaned[0] == cleaned[-1]
        and cleaned[0] in {'"', "'"}
    ):
        return cleaned[1:-1]

    try:
        if "." in cleaned:
            return float(cleaned)

        return int(cleaned)

    except ValueError:
        return cleaned


def load_simple_yaml(
    config_file: Path,
) -> dict[str, dict[str, Any]]:
    """
    读取任务四使用的简单 YAML。

    当前仅处理：

    section:
      key: value
    """

    if not config_file.exists():
        raise FileNotFoundError(
            f"找不到模型配置文件：{config_file}"
        )

    sections: dict[
        str,
        dict[str, Any],
    ] = {}

    current_section: str | None = None

    content = config_file.read_text(
        encoding="utf-8-sig"
    )

    for line_number, raw_line in enumerate(
        content.splitlines(),
        start=1,
    ):
        if "\t" in raw_line:
            raise ValueError(
                f"配置文件第 {line_number} 行含有 Tab，"
                "请统一使用空格缩进。"
            )

        line = raw_line.split(
            "#",
            maxsplit=1,
        )[0]

        if not line.strip():
            continue

        stripped = line.strip()

        if (
            not line.startswith(" ")
            and stripped.endswith(":")
        ):
            current_section = (
                stripped[:-1].strip()
            )

            sections.setdefault(
                current_section,
                {},
            )
            continue

        if current_section is None:
            continue

        if ":" not in stripped:
            continue

        key, value = stripped.split(
            ":",
            maxsplit=1,
        )

        sections[current_section][
            key.strip()
        ] = parse_scalar(value)

    return sections


def load_settings(
    env_file: Path = DEFAULT_ENV_FILE,
    config_file: Path = DEFAULT_CONFIG_FILE,
) -> LLMSettings:
    """加载并检查环境变量与统一模型配置。"""

    load_dotenv(
        dotenv_path=env_file,
        override=False,
    )

    api_key = (
        os.getenv("LLM_API_KEY", "")
        .strip()
    )

    base_url = (
        os.getenv("LLM_BASE_URL", "")
        .strip()
        .rstrip("/")
    )

    model = (
        os.getenv("LLM_MODEL", "")
        .strip()
    )

    missing_variables = []

    if not api_key:
        missing_variables.append(
            "LLM_API_KEY"
        )

    if not base_url:
        missing_variables.append(
            "LLM_BASE_URL"
        )

    if not model:
        missing_variables.append(
            "LLM_MODEL"
        )

    if missing_variables:
        raise ValueError(
            "缺少环境变量："
            f"{missing_variables}"
        )

    if not base_url.startswith(
        ("https://", "http://")
    ):
        raise ValueError(
            "LLM_BASE_URL 必须以 "
            "http:// 或 https:// 开头。"
        )

    config = load_simple_yaml(
        config_file
    )

    client_config = config.get(
        "client",
        {},
    )

    generation_config = config.get(
        "generation",
        {},
    )

    experiment_config = config.get(
        "experiment",
        {},
    )

    stream = bool(
        generation_config.get(
            "stream",
            False,
        )
    )

    if stream:
        raise ValueError(
            "当前统一实验客户端仅支持非流式调用，"
            "请将 stream 设置为 false。"
        )

    return LLMSettings(
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=float(
            client_config.get(
                "timeout_seconds",
                60,
            )
        ),
        max_retries=int(
            client_config.get(
                "max_retries",
                2,
            )
        ),
        temperature=float(
            generation_config.get(
                "temperature",
                0.1,
            )
        ),
        max_completion_tokens=int(
            generation_config.get(
                "max_completion_tokens",
                800,
            )
        ),
        stream=stream,
        enable_thinking=bool(
            generation_config.get(
                "enable_thinking",
                False,
            )
        ),
        seed=int(
            generation_config.get(
                "seed",
                42,
            )
        ),
        provider=str(
            experiment_config.get(
                "provider",
                "aliyun_bailian",
            )
        ),
        prompt_version=str(
            experiment_config.get(
                "prompt_version",
                "baseline_v1",
            )
        ),
    )


class QwenLLMClient:
    """统一的千问 OpenAI-compatible 客户端。"""

    def __init__(
        self,
        env_file: Path = DEFAULT_ENV_FILE,
        config_file: Path = DEFAULT_CONFIG_FILE,
    ) -> None:
        self.settings = load_settings(
            env_file=env_file,
            config_file=config_file,
        )

        self.client = OpenAI(
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
            timeout=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
        )

    def generate(
        self,
        user_prompt: str,
        system_prompt: str | None = None,
        json_mode: bool = False,
    ) -> LLMResult:
        """执行一次非流式模型生成。"""

        cleaned_user_prompt = (
            user_prompt or ""
        ).strip()

        if not cleaned_user_prompt:
            raise ValueError(
                "user_prompt 不能为空。"
            )

        messages: list[
            dict[str, str]
        ] = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt.strip(),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": cleaned_user_prompt,
            }
        )

        request_parameters: dict[
            str,
            Any,
        ] = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": (
                self.settings.temperature
            ),
            "max_completion_tokens": (
                self.settings
                .max_completion_tokens
            ),
            "seed": self.settings.seed,
            "stream": False,
            "extra_body": {
                "enable_thinking": (
                    self.settings
                    .enable_thinking
                )
            },
        }

        if json_mode:
            request_parameters[
                "response_format"
            ] = {
                "type": "json_object"
            }

        start_time = time.perf_counter()

        try:
            response = (
                self.client
                .chat
                .completions
                .create(
                    **request_parameters
                )
            )

        except AuthenticationError as exc:
            raise LLMClientError(
                "模型认证失败。请检查 API Key、"
                "业务空间和地域是否一致。"
            ) from exc

        except BadRequestError as exc:
            raise LLMClientError(
                "模型请求参数错误："
                f"{exc.message}"
            ) from exc

        except RateLimitError as exc:
            raise LLMClientError(
                "模型服务触发限流或额度限制。"
            ) from exc

        except APITimeoutError as exc:
            raise LLMClientError(
                "模型请求超时。"
            ) from exc

        except APIConnectionError as exc:
            raise LLMClientError(
                "无法连接模型服务。请检查 "
                "LLM_BASE_URL 和本地网络。"
            ) from exc

        except APIStatusError as exc:
            error_body = getattr(
                exc,
                "body",
                None,
            )

            if error_body is None:
                try:
                    error_body = exc.response.text
                except Exception:
                    error_body = str(exc)

            raise LLMClientError(
                "模型服务返回异常状态："
                f"HTTP {exc.status_code}；"
                f"服务端信息：{error_body}"
            ) from exc

        latency_seconds = round(
            time.perf_counter()
            - start_time,
            4,
        )

        if not response.choices:
            raise LLMClientError(
                "模型响应中没有 choices。"
            )

        choice = response.choices[0]

        content = (
            choice.message.content
            or ""
        ).strip()

        if not content:
            raise LLMClientError(
                "模型返回内容为空。"
            )

        usage = getattr(
            response,
            "usage",
            None,
        )

        prompt_tokens = int(
            getattr(
                usage,
                "prompt_tokens",
                0,
            )
            or 0
        )

        completion_tokens = int(
            getattr(
                usage,
                "completion_tokens",
                0,
            )
            or 0
        )

        total_tokens = int(
            getattr(
                usage,
                "total_tokens",
                0,
            )
            or 0
        )

        return LLMResult(
            content=content,
            model=(
                getattr(
                    response,
                    "model",
                    "",
                )
                or self.settings.model
            ),
            provider=(
                self.settings.provider
            ),
            prompt_version=(
                self.settings.prompt_version
            ),
            finish_reason=(
                choice.finish_reason
                or ""
            ),
            request_id=(
                getattr(
                    response,
                    "id",
                    "",
                )
                or ""
            ),
            prompt_tokens=prompt_tokens,
            completion_tokens=(
                completion_tokens
            ),
            total_tokens=total_tokens,
            latency_seconds=(
                latency_seconds
            ),
            temperature=(
                self.settings.temperature
            ),
            max_completion_tokens=(
                self.settings
                .max_completion_tokens
            ),
            enable_thinking=(
                self.settings
                .enable_thinking
            ),
            seed=self.settings.seed,
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "测试统一千问大模型客户端。"
        )
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="运行最小连接测试",
    )

    parser.add_argument(
        "--prompt",
        type=str,
        default="",
        help="自定义用户提示词",
    )

    args = parser.parse_args()

    if args.test:
        prompt = (
            "请只回复“连接成功”，"
            "不要添加其他内容。"
        )
    else:
        prompt = args.prompt.strip()

    if not prompt:
        print(
            "请使用 --test 或 --prompt 输入内容。"
        )
        return 1

    try:
        client = QwenLLMClient()

        result = client.generate(
            user_prompt=prompt
        )

    except (
        FileNotFoundError,
        ValueError,
        LLMClientError,
    ) as exc:
        print(
            f"模型调用失败：{exc}"
        )
        return 1

    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())