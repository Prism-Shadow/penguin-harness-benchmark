"""Harbor Codex adapter using the locally installed runtime bundle."""
import os
from pathlib import Path
from harbor.agents.installed.codex import Codex


class ToolkitCodex(Codex):
    def _load_base_config(self):
        config = super()._load_base_config()
        config.setdefault('model_context_window', 1_048_576)
        config.setdefault('model_auto_compact_token_limit', 800_000)
        config.setdefault('model_provider', 'deepseek')
        config.setdefault('model_providers', {}).setdefault('deepseek', {
            'name': 'DeepSeek',
            'base_url': 'https://api.deepseek.com',
            'wire_api': 'responses',
            'requires_openai_auth': True,
        })
        return config

    async def exec_as_agent(self, environment, command, env=None, cwd=None, timeout_sec=None):
        if 'codex exec ' in command and env:
            env = dict(env)
            for name in ('OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN'):
                env.pop(name, None)
        return await super().exec_as_agent(environment, command, env=env, cwd=cwd, timeout_sec=timeout_sec)

    async def install(self, environment):
        if await self._installed_codex_satisfies_version(environment):
            return
        await self.exec_as_root(environment, command='mkdir -p /opt/codex-runtime')
        await environment.upload_dir('/home/penguin/gdpevo-codex-runtime', '/opt/codex-runtime')
        await self.exec_as_root(environment, command=(
            'ln -sf /opt/codex-runtime/bin/node /usr/local/bin/node && '
            'ln -sf /opt/codex-runtime/bin/codex /usr/local/bin/codex && '
            'ln -sf /opt/codex-runtime/bin/npm /usr/local/bin/npm && '
            'ln -sf /opt/codex-runtime/lib/node_modules/@openai/codex/node_modules/'
            '@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/codex-path/rg /usr/local/bin/rg && '
            'command -v bash && command -v curl && codex --version && rg --version'
        ))


class ResumeToolkitCodex(ToolkitCodex):
    async def run(self, instruction, environment, context):
        source = Path(os.environ['GDPEVO_RESTORE_SUBMISSION'])
        if not source.is_dir():
            raise ValueError('saved training submission is missing')
        await self.exec_as_root(environment, command='mkdir -p /tmp/gdpevo-restore')
        await environment.upload_dir(source, '/tmp/gdpevo-restore')
        await self.exec_as_agent(environment, command='cp -r /tmp/gdpevo-restore/. /app/submission/')
        await super().run(instruction, environment, context)
