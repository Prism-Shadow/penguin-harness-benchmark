import asyncio
from types import SimpleNamespace

import pytest

from test_support import load_usage_pipeline, run


class ChatTransport:
    def __init__(self):
        self.mdl = SimpleNamespace(last_usage=None)

    def clone(self):
        return ChatTransport()

    async def async_chat(self, system, history, gen_conf=None, **kwargs):
        await asyncio.sleep(0)
        if system == 'fail':
            raise RuntimeError('transport unavailable')
        self.mdl.last_usage = {'prompt_tokens': 3, 'completion_tokens': 4, 'total_tokens': 7}
        return system

    async def async_chat_streamly(self, system, history, gen_conf=None, **kwargs):
        yield await self.async_chat(system, history, gen_conf, **kwargs)

    async_chat_streamly_delta = async_chat_streamly


def test_production_ragtools_accounts_calls_streams_and_failures():
    stats_module, production = load_usage_pipeline()
    tools = production.RAGTools(['tenant'], ChatTransport())
    async def exercise():
        with stats_module.phase('research'):
            assert await tools.chat_mdl.async_chat('response', []) == 'response'
            assert [part async for part in tools.chat_mdl.async_chat_streamly('stream', [])] == ['stream']
            assert [part async for part in tools.chat_mdl.async_chat_streamly_delta('delta', [])] == ['delta']
            with pytest.raises(RuntimeError, match='transport unavailable'):
                await tools.chat_mdl.async_chat('fail', [])
            for method in (tools.chat_mdl.async_chat_streamly, tools.chat_mdl.async_chat_streamly_delta):
                with pytest.raises(RuntimeError, match='transport unavailable'):
                    async for _ in method('fail', []):
                        pass
    run(exercise())
    row = tools.llm_stats.snapshot()['research']
    assert row['calls'] == 6
    assert row['total_tokens'] == 21
    assert row['prompt_tokens'] == 9
    assert row['completion_tokens'] == 12


def test_concurrent_runs_restore_phase_and_keep_usage_independent():
    stats_module, production = load_usage_pipeline()
    first = production.RAGTools(['tenant'], ChatTransport())
    second = production.RAGTools(['tenant'], ChatTransport())
    async def branch(label, count):
        sink = stats_module.LLMUsageStats()
        with stats_module.using_stats(sink), stats_module.phase(label):
            for index in range(count):
                await first.chat_mdl.async_chat(str(index), [])
            with stats_module.phase('nested'):
                await first.chat_mdl.async_chat('nested', [])
            await first.chat_mdl.async_chat('restored', [])
        return sink.snapshot()
    async def exercise():
        snapshots = await asyncio.gather(branch('one', 1), branch('two', 2))
        await first.chat_mdl.async_chat('outside', [])
        return snapshots
    snapshots = run(exercise())
    assert 'one' in snapshots[0] and 'two' in snapshots[1], snapshots
    assert snapshots[0]['one']['calls'] == 2
    assert snapshots[1]['two']['calls'] == 3
    assert 'two' not in snapshots[0] and 'one' not in snapshots[1]
    assert all(snapshot['nested']['total_tokens'] == 7 for snapshot in snapshots)
    assert first.llm_stats.snapshot()['unknown']['calls'] == 1
    assert second.llm_stats.snapshot() == {}
