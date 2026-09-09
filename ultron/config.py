"""Configuration loading.

Reads `.env` from the project root (a minimal hand-rolled parser keeps the
runtime dependency tree to just the model SDK — no python-dotenv). Real
environment variables always take precedence over values in `.env`. No
secrets are ever hardcoded here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

SUPPORTED_PROVIDERS = (
    "gemini",
    "nvidia",
    "openrouter",
    "grok",
    "openai",
    "azure_openai",
    "anthropic",
    "cohere",
    "mistral",
    "perplexity",
    "bedrock",
)

DEFAULT_SYSTEM_PROMPT = """You are Ultron, a JARVIS-style personal desktop assistant running locally on Windows.

Personality: calm, intelligent, confident, professional, proactive, honest, context-aware, and slightly witty. Never arrogant, never verbose. Be concise by default; give detail only when the task warrants it. Distinguish facts from assumptions. Push back on bad plans instead of blindly agreeing.

Priorities: coding and development (~40%), desktop automation / computer operations (~30%), general assistance (~20%), research / web (~10%).

Capabilities via tools:
- Time: get_current_time (supports any timezone, e.g. 'Asia/Kolkata' for IST)
- Browser: navigate_url, click_element, fill_form, scroll_page, press_key, browser_type, hover_element, wait_element, read_page, get_page_links, browser_screenshot
- Files: read_file, create_file, search_files
- Apps: open_app, close_app
- System: get_system_info, take_screenshot, clipboard
- Voice: speak, listen
- Web: open_url, http_request
- Calendar/Notes/Reminders: create_calendar_event, create_note, create_reminder

When the user asks for the time, ALWAYS use the get_current_time tool. Never say you don't have access to time.
When the user asks to open a website, use navigate_url to open it in the browser, then use click_element, fill_form, browser_type, press_key to interact with the page.
Only use a tool when it genuinely serves the user's request; otherwise answer directly. When you use a tool, report the result accurately and honestly. Never claim an action succeeded if it did not."""


class ConfigError(RuntimeError):
    """Raised when the environment is unusable (missing key, bad provider, etc.)."""


def _parse_env_text(text: str) -> Dict[str, str]:
    """Minimal .env parser: KEY=VALUE lines, # comments, quote stripping."""
    result: Dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            result[key] = value
    return result


def load_dotenv(env_file: str | Path | None = None) -> Dict[str, str]:
    """Load KEY=VALUE pairs from an .env file (does not touch os.environ)."""
    path = Path(env_file) if env_file else (Path.cwd() / ".env")
    if not path.is_file():
        return {}
    try:
        return _parse_env_text(path.read_text(encoding="utf-8"))
    except OSError:
        return {}


@dataclass(frozen=True)
class LLMConfig:
    provider: str = "gemini"
    gemini_api_key: str = ""
    nvidia_api_key: str = ""
    openrouter_api_key: str = ""
    grok_api_key: str = ""
    openai_api_key: str = ""
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_version: str = "2024-02-01"
    anthropic_api_key: str = ""
    cohere_api_key: str = ""
    mistral_api_key: str = ""
    perplexity_api_key: str = ""
    bedrock_region: str = "us-east-1"
    bedrock_access_key: str = ""
    bedrock_secret_key: str = ""
    model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    temperature: float = 0.3
    api_base_url: str = ""
    provider_fallback: str = ""


@dataclass(frozen=True)
class MemoryConfig:
    file: Path = field(default_factory=lambda: Path.home() / ".ultron" / "memory.jsonl")
    enabled: bool = True
    retrieval_limit: int = 10
    relevance_threshold: float = 0.1


@dataclass(frozen=True)
class SecurityConfig:
    require_permission: bool = False
    allowed_filesystem_roots: str = ""
    sandbox_directory: str = ""
    permission_policy: str = "default"
    command_timeout: int = 30
    max_execution_time: int = 300
    audit_log_path: Path = field(default_factory=lambda: Path.home() / ".ultron" / "audit.log")
    audit_log_enabled: bool = True


@dataclass(frozen=True)
class ExecutionConfig:
    max_tool_iterations: int = 8
    tool_timeout: int = 60
    max_plan_steps: int = 20
    max_retries: int = 3
    semantic_verification_enabled: bool = True
    agent_execution_limit: int = 8
    browser_enabled: bool = True
    execution_state_enabled: bool = True
    execution_state_file: str = ""
    max_concurrent_tasks: int = 5


@dataclass(frozen=True)
class BrainModelConfig:
    provider: str = "openrouter"
    model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    temperature: float = 0.3
    max_tokens: int = 8192


@dataclass(frozen=True)
class BrainConfig:
    planning: BrainModelConfig = field(default_factory=BrainModelConfig)
    research: BrainModelConfig = field(default_factory=BrainModelConfig)
    coding: BrainModelConfig = field(default_factory=BrainModelConfig)
    computer: BrainModelConfig = field(default_factory=BrainModelConfig)
    verification: BrainModelConfig = field(default_factory=BrainModelConfig)
    fast: BrainModelConfig = field(default_factory=BrainModelConfig)


class Config:
    """Grouped, typed configuration for Ultron with flat property fallback."""

    def __init__(
        self,
        llm: LLMConfig | None = None,
        memory: MemoryConfig | None = None,
        security: SecurityConfig | None = None,
        execution: ExecutionConfig | None = None,
        brain: BrainConfig | None = None,
        log_level: str = "INFO",
        debug_mode: bool = False,
        **kwargs: Any,
    ) -> None:
        llm_keys = set(LLMConfig.__dataclass_fields__.keys())
        memory_keys = set(MemoryConfig.__dataclass_fields__.keys())
        memory_keys.add("memory_file")
        memory_keys.add("memory_enabled")
        memory_keys.add("memory_retrieval_limit")
        memory_keys.add("memory_relevance_threshold")
        security_keys = set(SecurityConfig.__dataclass_fields__.keys())
        execution_keys = set(ExecutionConfig.__dataclass_fields__.keys())
        brain_keys = {"brain", "brain_config"}

        llm_args = {k: v for k, v in kwargs.items() if k in llm_keys}
        memory_args = {}
        for k, v in kwargs.items():
            if k == "memory_file":
                memory_args["file"] = v
            elif k == "memory_enabled":
                memory_args["enabled"] = v
            elif k == "memory_retrieval_limit":
                memory_args["retrieval_limit"] = v
            elif k == "memory_relevance_threshold":
                memory_args["relevance_threshold"] = v
            elif k in memory_keys:
                memory_args[k] = v

        security_args = {k: v for k, v in kwargs.items() if k in security_keys}
        execution_args = {k: v for k, v in kwargs.items() if k in execution_keys}
        brain_args = {k: v for k, v in kwargs.items() if k in brain_keys}

        self.llm = llm if llm is not None else LLMConfig(**llm_args)
        self.memory = memory if memory is not None else MemoryConfig(**memory_args)
        self.security = security if security is not None else SecurityConfig(**security_args)
        self.execution = execution if execution is not None else ExecutionConfig(**execution_args)
        self.brain = brain if brain is not None else (
            brain_args.get("brain") if "brain" in brain_args else
            brain_args.get("brain_config") if "brain_config" in brain_args else
            BrainConfig()
        )
        self.log_level = log_level
        self.debug_mode = debug_mode

    # Flat properties for 100% backward compatibility
    @property
    def provider(self) -> str:
        return self.llm.provider

    @property
    def gemini_api_key(self) -> str:
        return self.llm.gemini_api_key

    @property
    def nvidia_api_key(self) -> str:
        return self.llm.nvidia_api_key

    @property
    def openrouter_api_key(self) -> str:
        return self.llm.openrouter_api_key

    @property
    def grok_api_key(self) -> str:
        return self.llm.grok_api_key

    @property
    def model(self) -> str:
        return self.llm.model

    @property
    def system_prompt(self) -> str:
        return self.llm.system_prompt

    @property
    def temperature(self) -> float:
        return self.llm.temperature

    @property
    def api_base_url(self) -> str:
        return self.llm.api_base_url

    @property
    def provider_fallback(self) -> str:
        return self.llm.provider_fallback

    @property
    def memory_file(self) -> Path:
        return self.memory.file

    @property
    def memory_enabled(self) -> bool:
        return self.memory.enabled

    @property
    def memory_retrieval_limit(self) -> int:
        return self.memory.retrieval_limit

    @property
    def memory_relevance_threshold(self) -> float:
        return self.memory.relevance_threshold

    @property
    def require_permission(self) -> bool:
        return self.security.require_permission

    @property
    def allowed_filesystem_roots(self) -> str:
        return self.security.allowed_filesystem_roots

    @property
    def sandbox_directory(self) -> str:
        return self.security.sandbox_directory

    @property
    def permission_policy(self) -> str:
        return self.security.permission_policy

    @property
    def command_timeout(self) -> int:
        return self.security.command_timeout

    @property
    def max_execution_time(self) -> int:
        return self.security.max_execution_time

    @property
    def audit_log_path(self) -> Path:
        return self.security.audit_log_path

    @property
    def audit_log_enabled(self) -> bool:
        return self.security.audit_log_enabled

    @property
    def max_tool_iterations(self) -> int:
        return self.execution.max_tool_iterations

    @property
    def tool_timeout(self) -> int:
        return self.execution.tool_timeout

    @property
    def max_plan_steps(self) -> int:
        return self.execution.max_plan_steps

    @property
    def max_retries(self) -> int:
        return self.execution.max_retries

    @property
    def semantic_verification_enabled(self) -> bool:
        return self.execution.semantic_verification_enabled

    @property
    def agent_execution_limit(self) -> int:
        return self.execution.agent_execution_limit

    @property
    def browser_enabled(self) -> bool:
        return self.execution.browser_enabled

    @property
    def execution_state_enabled(self) -> bool:
        return self.execution.execution_state_enabled

    @property
    def execution_state_file(self) -> str:
        return self.execution.execution_state_file

    @property
    def max_concurrent_tasks(self) -> int:
        return self.execution.max_concurrent_tasks


def _as_int(name: str, value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} must be an integer, got: {value!r}") from None


def _as_float(name: str, value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} must be a number, got: {value!r}") from None


def load_config(env_file: str | Path | None = None, environ: Dict[str, str] | None = None) -> Config:
    """Build a Config from `.env` (project root by default) + os.environ.

    Resolution order per key: real environment variable > .env > default.
    """
    environ = dict(os.environ if environ is None else environ)
    dotenv = load_dotenv(env_file)

    def get(key: str, default: str = "") -> str:
        if key in environ:
            return environ[key]
        if key in dotenv:
            return dotenv[key]
        return default

    provider = get("ULTRON_PROVIDER", "gemini").strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise ConfigError(
            f"ULTRON_PROVIDER={provider!r} is not supported in V1. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}."
        )

    api_key = get("GEMINI_API_KEY", "").strip()
    nvidia_api_key = get("ULTRON_NVIDIA_API_KEY", "").strip()
    openrouter_api_key = get("ULTRON_OPENROUTER_API_KEY", "").strip()
    grok_api_key = get("ULTRON_GROK_API_KEY", "").strip()
    if provider == "gemini" and not api_key:
        raise ConfigError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export GEMINI_API_KEY."
        )
    if provider == "nvidia" and not nvidia_api_key:
        raise ConfigError(
            "ULTRON_NVIDIA_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export ULTRON_NVIDIA_API_KEY."
        )
    if provider == "openrouter" and not openrouter_api_key:
        raise ConfigError(
            "ULTRON_OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export ULTRON_OPENROUTER_API_KEY."
        )
    if provider == "grok" and not grok_api_key:
        raise ConfigError(
            "ULTRON_GROK_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export ULTRON_GROK_API_KEY."
        )

    openai_api_key = get("OPENAI_API_KEY", "").strip()
    azure_openai_api_key = get("AZURE_OPENAI_API_KEY", "").strip()
    azure_openai_endpoint = get("AZURE_OPENAI_ENDPOINT", "").strip()
    azure_openai_deployment = get("AZURE_OPENAI_DEPLOYMENT", "").strip()
    azure_openai_version = get("AZURE_OPENAI_VERSION", "2024-02-01").strip()
    anthropic_api_key = get("ANTHROPIC_API_KEY", "").strip()
    cohere_api_key = get("COHERE_API_KEY", "").strip()
    mistral_api_key = get("MISTRAL_API_KEY", "").strip()
    perplexity_api_key = get("PERPLEXITY_API_KEY", "").strip()
    bedrock_region = get("AWS_BEDROCK_REGION", "us-east-1").strip()
    bedrock_access_key = get("AWS_ACCESS_KEY_ID", "").strip()
    bedrock_secret_key = get("AWS_SECRET_ACCESS_KEY", "").strip()

    if provider == "openai" and not openai_api_key:
        raise ConfigError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export OPENAI_API_KEY."
        )
    if provider == "azure_openai" and not azure_openai_api_key:
        raise ConfigError(
            "AZURE_OPENAI_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export AZURE_OPENAI_API_KEY."
        )
    if provider == "anthropic" and not anthropic_api_key:
        raise ConfigError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export ANTHROPIC_API_KEY."
        )
    if provider == "cohere" and not cohere_api_key:
        raise ConfigError(
            "COHERE_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export COHERE_API_KEY."
        )
    if provider == "mistral" and not mistral_api_key:
        raise ConfigError(
            "MISTRAL_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export MISTRAL_API_KEY."
        )
    if provider == "perplexity" and not perplexity_api_key:
        raise ConfigError(
            "PERPLEXITY_API_KEY is not set. Copy .env.example to .env and add your key, "
            "or export PERPLEXITY_API_KEY."
        )
    if provider == "bedrock":
        if not bedrock_access_key or not bedrock_secret_key:
            raise ConfigError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are not set. "
                "Copy .env.example to .env and add your keys, "
                "or export AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
            )

    audit = get("ULTRON_AUDIT_LOG", "").strip()
    audit_path = Path(audit).expanduser() if audit else Path.home() / ".ultron" / "audit.log"

    debug = get("ULTRON_DEBUG", "").strip().lower() in ("1", "true", "yes")

    llm = LLMConfig(
        provider=provider,
        gemini_api_key=api_key,
        nvidia_api_key=nvidia_api_key,
        openrouter_api_key=openrouter_api_key,
        grok_api_key=grok_api_key,
        openai_api_key=openai_api_key,
        azure_openai_api_key=azure_openai_api_key,
        azure_openai_endpoint=azure_openai_endpoint,
        azure_openai_deployment=azure_openai_deployment,
        azure_openai_version=azure_openai_version,
        anthropic_api_key=anthropic_api_key,
        cohere_api_key=cohere_api_key,
        mistral_api_key=mistral_api_key,
        perplexity_api_key=perplexity_api_key,
        bedrock_region=bedrock_region,
        bedrock_access_key=bedrock_access_key,
        bedrock_secret_key=bedrock_secret_key,
        model=get("ULTRON_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash",
        system_prompt=get("ULTRON_SYSTEM_PROMPT", "").strip() or DEFAULT_SYSTEM_PROMPT,
        temperature=_as_float("ULTRON_TEMPERATURE", get("ULTRON_TEMPERATURE", "0.3"), 0.3),
        api_base_url=get("ULTRON_API_BASE_URL", "").strip(),
        provider_fallback=get("ULTRON_PROVIDER_FALLBACK", "").strip(),
    )

    memory_file = (
        Path(get("ULTRON_MEMORY_FILE", "")).expanduser()
        if get("ULTRON_MEMORY_FILE", "").strip()
        else Path.home() / ".ultron" / "memory.jsonl"
    )

    memory = MemoryConfig(
        file=memory_file,
        enabled=get("ULTRON_MEMORY_ENABLED", "true").strip().lower() in ("1", "true", "yes"),
        retrieval_limit=_as_int("ULTRON_MEMORY_RETRIEVAL_LIMIT", get("ULTRON_MEMORY_RETRIEVAL_LIMIT", "10"), 10),
        relevance_threshold=_as_float("ULTRON_MEMORY_RELEVANCE_THRESHOLD", get("ULTRON_MEMORY_RELEVANCE_THRESHOLD", "0.1"), 0.1),
    )

    security = SecurityConfig(
        require_permission=get("ULTRON_REQUIRE_PERMISSION", "").strip().lower() in ("1", "true", "yes"),
        allowed_filesystem_roots=get("ULTRON_ALLOWED_FILESYSTEM_ROOTS", "").strip(),
        sandbox_directory=get("ULTRON_SANDBOX_DIRECTORY", "").strip(),
        permission_policy=get("ULTRON_PERMISSION_POLICY", "default").strip(),
        command_timeout=_as_int("ULTRON_COMMAND_TIMEOUT", get("ULTRON_COMMAND_TIMEOUT", "30"), 30),
        max_execution_time=_as_int("ULTRON_MAX_EXECUTION_TIME", get("ULTRON_MAX_EXECUTION_TIME", "300"), 300),
        audit_log_path=audit_path,
        audit_log_enabled=get("ULTRON_AUDIT_LOG_ENABLED", "true").strip().lower() in ("1", "true", "yes"),
    )

    execution = ExecutionConfig(
        max_tool_iterations=_as_int("ULTRON_MAX_TOOL_ITERATIONS", get("ULTRON_MAX_TOOL_ITERATIONS", "8"), 8),
        tool_timeout=_as_int("ULTRON_TOOL_TIMEOUT", get("ULTRON_TOOL_TIMEOUT", "60"), 60),
        max_plan_steps=_as_int("ULTRON_MAX_PLAN_STEPS", get("ULTRON_MAX_PLAN_STEPS", "20"), 20),
        max_retries=_as_int("ULTRON_MAX_RETRIES", get("ULTRON_MAX_RETRIES", "3"), 3),
        semantic_verification_enabled=get("ULTRON_SEMANTIC_VERIFICATION", "true").strip().lower() in ("1", "true", "yes"),
        agent_execution_limit=_as_int("ULTRON_AGENT_EXECUTION_LIMIT", get("ULTRON_AGENT_EXECUTION_LIMIT", "8"), 8),
        browser_enabled=get("ULTRON_BROWSER_ENABLED", "true").strip().lower() in ("1", "true", "yes"),
        execution_state_enabled=get("ULTRON_EXECUTION_STATE_ENABLED", "true").strip().lower() in ("1", "true", "yes"),
        execution_state_file=get("ULTRON_EXECUTION_STATE_FILE", "").strip(),
        max_concurrent_tasks=_as_int("ULTRON_MAX_CONCURRENT_TASKS", get("ULTRON_MAX_CONCURRENT_TASKS", "5"), 5),
    )

    brain = BrainConfig(
        planning=BrainModelConfig(
            provider=get("JARVIS_PLANNER_PROVIDER", "openrouter").strip().lower() or "openrouter",
            model=get("JARVIS_PLANNER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free").strip() or "nvidia/nemotron-3-ultra-550b-a55b:free",
            temperature=_as_float("JARVIS_PLANNER_TEMPERATURE", get("JARVIS_PLANNER_TEMPERATURE", "0.3"), 0.3),
            max_tokens=_as_int("JARVIS_PLANNER_MAX_TOKENS", get("JARVIS_PLANNER_MAX_TOKENS", "16384"), 16384),
        ),
        research=BrainModelConfig(
            provider=get("JARVIS_RESEARCH_PROVIDER", "openrouter").strip().lower() or "openrouter",
            model=get("JARVIS_RESEARCH_MODEL", "nvidia/nemotron-3-super-120b-a12b:free").strip() or "nvidia/nemotron-3-super-120b-a12b:free",
            temperature=_as_float("JARVIS_RESEARCH_TEMPERATURE", get("JARVIS_RESEARCH_TEMPERATURE", "0.3"), 0.3),
            max_tokens=_as_int("JARVIS_RESEARCH_MAX_TOKENS", get("JARVIS_RESEARCH_MAX_TOKENS", "16384"), 16384),
        ),
        coding=BrainModelConfig(
            provider=get("JARVIS_CODING_PROVIDER", "openrouter").strip().lower() or "openrouter",
            model=get("JARVIS_CODING_MODEL", "poolside/laguna-s-2.1:free").strip() or "poolside/laguna-s-2.1:free",
            temperature=_as_float("JARVIS_CODING_TEMPERATURE", get("JARVIS_CODING_TEMPERATURE", "0.3"), 0.3),
            max_tokens=_as_int("JARVIS_CODING_MAX_TOKENS", get("JARVIS_CODING_MAX_TOKENS", "16384"), 16384),
        ),
        computer=BrainModelConfig(
            provider=get("JARVIS_COMPUTER_PROVIDER", "openrouter").strip().lower() or "openrouter",
            model=get("JARVIS_COMPUTER_MODEL", "thinkingmachines/inkling:free").strip() or "thinkingmachines/inkling:free",
            temperature=_as_float("JARVIS_COMPUTER_TEMPERATURE", get("JARVIS_COMPUTER_TEMPERATURE", "0.3"), 0.3),
            max_tokens=_as_int("JARVIS_COMPUTER_MAX_TOKENS", get("JARVIS_COMPUTER_MAX_TOKENS", "16384"), 16384),
        ),
        verification=BrainModelConfig(
            provider=get("JARVIS_VERIFICATION_PROVIDER", "openrouter").strip().lower() or "openrouter",
            model=get("JARVIS_VERIFICATION_MODEL", "nvidia/nemotron-3.5-lightning:free").strip() or "nvidia/nemotron-3.5-lightning:free",
            temperature=_as_float("JARVIS_VERIFICATION_TEMPERATURE", get("JARVIS_VERIFICATION_TEMPERATURE", "0.3"), 0.3),
            max_tokens=_as_int("JARVIS_VERIFICATION_MAX_TOKENS", get("JARVIS_VERIFICATION_MAX_TOKENS", "8192"), 8192),
        ),
        fast=BrainModelConfig(
            provider=get("JARVIS_FAST_PROVIDER", "openrouter").strip().lower() or "openrouter",
            model=get("JARVIS_FAST_MODEL", "cohere/north-mini-code:free").strip() or "cohere/north-mini-code:free",
            temperature=_as_float("JARVIS_FAST_TEMPERATURE", get("JARVIS_FAST_TEMPERATURE", "0.3"), 0.3),
            max_tokens=_as_int("JARVIS_FAST_MAX_TOKENS", get("JARVIS_FAST_MAX_TOKENS", "4096"), 4096),
        ),
    )

    return Config(
        llm=llm,
        memory=memory,
        security=security,
        execution=execution,
        brain=brain,
        log_level="DEBUG" if debug else (get("LOG_LEVEL", "INFO").strip().upper() or "INFO"),
        debug_mode=debug,
    )
