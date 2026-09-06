"""Harbor grok-build that uses host grok.com OAuth (~/.grok/auth.json).

Harbor's stock grok-build agent requires XAI_API_KEY. This wrapper copies the
local OAuth session into the agent container and runs grok headless without an
API key. Session token takes precedence over XAI_API_KEY when both exist.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from harbor.agents.installed.base import with_prompt_template
from harbor.agents.installed.grok_build import GrokBuild
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.trial.paths import EnvironmentPaths


class GrokBuildOAuth(GrokBuild):
    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        auth_path = Path.home() / ".grok" / "auth.json"
        if not auth_path.is_file():
            raise ValueError(
                "No grok OAuth session at ~/.grok/auth.json. Run `grok login --oauth`."
            )

        escaped_instruction = shlex.quote(instruction)
        escaped_auth = shlex.quote(auth_path.read_text())

        await self.exec_as_agent(
            environment, command=self._build_write_config_command()
        )
        await self.exec_as_agent(
            environment,
            command=(
                "mkdir -p ~/.grok && "
                f"printf '%s' {escaped_auth} > ~/.grok/auth.json && "
                "chmod 600 ~/.grok/auth.json"
            ),
        )

        env = {
            "GROK_DISABLE_AUTOUPDATER": "1",
            "GROK_LOG_FILE": (
                EnvironmentPaths.agent_dir / self._CLI_LOG_FILENAME
            ).as_posix(),
            "RUST_LOG": self._get_env("RUST_LOG") or "warn",
        }

        try:
            await self.exec_as_agent(
                environment,
                command=self._build_run_script(escaped_instruction),
                env=env,
            )
        finally:
            try:
                sessions_target = EnvironmentPaths.agent_dir / "sessions"
                await self.exec_as_agent(
                    environment,
                    command=(
                        f"mkdir -p {EnvironmentPaths.agent_dir.as_posix()}\n"
                        'if [ -d "$HOME/.grok/sessions" ]; then\n'
                        f"  rm -rf {sessions_target.as_posix()}\n"
                        f'  cp -R "$HOME/.grok/sessions" {sessions_target.as_posix()}\n'
                        "fi"
                    ),
                )
            except Exception:
                self.logger.debug("Failed to copy grok session files", exc_info=True)
