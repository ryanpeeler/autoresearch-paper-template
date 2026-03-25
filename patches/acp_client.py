"""ACP (Agent Client Protocol) LLM client via claude CLI.

Uses the Claude Code CLI directly in --print mode for non-interactive,
single-shot prompts. No acpx or @zed-industries/claude-agent-acp dependency.

Each stage call is stateless (no persistent session), but the pipeline
context is maintained through the prompt content itself.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Any

from researchclaw.llm.client import LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class ACPConfig:
    """Configuration for ACP agent connection."""

    agent: str = "claude"
    cwd: str = "."
    acpx_command: str = ""  # unused, kept for config compat
    session_name: str = "researchclaw"
    timeout_sec: int = 1800  # per-prompt timeout


def _find_claude() -> str | None:
    """Find the claude CLI binary on PATH."""
    return shutil.which("claude")


class ACPClient:
    """LLM client that uses the Claude Code CLI directly.

    Sends prompts via ``claude --print`` for non-interactive execution.
    Each call is independent — no persistent session required.
    """

    def __init__(self, acp_config: ACPConfig) -> None:
        self.config = acp_config
        self._claude: str | None = None

    @classmethod
    def from_rc_config(cls, rc_config: Any) -> ACPClient:
        """Build from a ResearchClaw ``RCConfig``."""
        acp = rc_config.llm.acp
        return cls(ACPConfig(
            agent=acp.agent,
            cwd=acp.cwd,
            acpx_command=getattr(acp, "acpx_command", ""),
            session_name=getattr(acp, "session_name", "researchclaw"),
            timeout_sec=getattr(acp, "timeout_sec", 1800),
        ))

    # ------------------------------------------------------------------
    # Public interface (matches LLMClient)
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        json_mode: bool = False,
        system: str | None = None,
        strip_thinking: bool = False,
    ) -> LLMResponse:
        """Send a prompt and return Claude's response."""
        prompt_text = self._messages_to_prompt(messages, system=system)
        content = self._send_prompt(prompt_text, json_mode=json_mode)
        if strip_thinking:
            from researchclaw.utils.thinking_tags import strip_thinking_tags
            content = strip_thinking_tags(content)
        return LLMResponse(
            content=content,
            model=f"acp:{self.config.agent}",
            finish_reason="stop",
        )

    def preflight(self) -> tuple[bool, str]:
        """Check that claude CLI is available and authenticated."""
        claude = self._resolve_claude()
        if not claude:
            return False, (
                "claude CLI not found. Install: npm i -g @anthropic-ai/claude-code"
            )
        # Check auth status
        try:
            result = subprocess.run(
                [claude, "auth", "status"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and "loggedIn" in result.stdout:
                return True, "OK - Claude CLI authenticated"
            return False, f"Claude CLI auth check failed: {result.stdout.strip()}"
        except Exception as exc:  # noqa: BLE001
            return False, f"Claude CLI auth check failed: {exc}"

    def close(self) -> None:
        """No-op — stateless client, nothing to close."""
        pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_claude(self) -> str | None:
        """Resolve the claude binary path (cached)."""
        if self._claude:
            return self._claude
        self._claude = _find_claude()
        return self._claude

    def _abs_cwd(self) -> str:
        return os.path.abspath(self.config.cwd)

    _MAX_RETRIES = 2

    def _send_prompt(self, prompt: str, *, json_mode: bool = False) -> str:
        """Send a prompt via claude --print, piping through stdin.

        Always uses stdin to avoid CLI argument length limits.
        Retries on transient failures.
        """
        claude = self._resolve_claude()
        if not claude:
            raise RuntimeError("claude CLI not found")

        last_exc: RuntimeError | None = None
        for attempt in range(1 + self._MAX_RETRIES):
            try:
                return self._send_prompt_stdin(claude, prompt, json_mode=json_mode)
            except RuntimeError as exc:
                last_exc = exc
                if attempt < self._MAX_RETRIES:
                    logger.warning(
                        "Claude prompt failed (%s), retrying (attempt %d/%d)...",
                        exc, attempt + 1, self._MAX_RETRIES,
                    )

        raise last_exc  # type: ignore[misc]

    def _send_prompt_stdin(self, claude: str, prompt: str, *, json_mode: bool = False) -> str:
        """Send prompt via temp file to claude --print.

        Always writes to a temp file for reliability with large prompts,
        then passes the file path as the positional argument.
        """
        fd, prompt_path = tempfile.mkstemp(suffix=".md", prefix="rc_prompt_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(prompt)

            cmd = [
                claude, "--print",
                "--output-format", "text",
                "--max-turns", "2",
                "--allowed-tools", "Read",
                "-",  # read from stdin
            ]
            if json_mode:
                cmd.extend(["--append-system-prompt",
                             "You MUST respond with valid JSON only. "
                             "Do not include any text outside the JSON object."])

            stdin_prompt = (
                f"Read the file at {prompt_path} in its entirety. "
                f"Follow ALL instructions contained in that file and "
                f"respond exactly as requested. Do NOT summarize, "
                f"just produce the requested output."
            )

            try:
                result = subprocess.run(
                    cmd,
                    input=stdin_prompt,
                    capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=self.config.timeout_sec,
                    cwd=self._abs_cwd(),
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError(
                    f"Claude prompt timed out after {self.config.timeout_sec}s"
                ) from exc

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                stdout = (result.stdout or "").strip()
                logger.error("Claude failed (exit %d). stderr: %s | stdout (first 500): %s",
                             result.returncode, stderr, stdout[:500])
                raise RuntimeError(
                    f"Claude prompt failed (exit {result.returncode}): {stderr or stdout[:200]}"
                )

            return (result.stdout or "").strip()
        finally:
            try:
                os.unlink(prompt_path)
            except OSError:
                pass

    @staticmethod
    def _messages_to_prompt(
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
    ) -> str:
        """Flatten a chat-messages list into a single text prompt."""
        parts: list[str] = []
        if system:
            parts.append(f"[System]\n{system}")
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"[System]\n{content}")
            elif role == "assistant":
                parts.append(f"[Previous Response]\n{content}")
            else:
                parts.append(content)
        return "\n\n".join(parts)
