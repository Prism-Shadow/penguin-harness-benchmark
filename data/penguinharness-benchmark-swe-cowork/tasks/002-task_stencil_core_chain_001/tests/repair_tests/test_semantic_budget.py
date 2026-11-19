import copy
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SERVICE = Path(os.environ.get('WORKPLACE_SERVICE_CODE', str(Path(__file__).resolve().parents[2] / 'environment/workplace-service')))
ORIGINAL = Path(os.environ.get('WORKPLACE_ORIGINAL_ROOT', str(SERVICE / 'original')))
sys.path.insert(0, str(SERVICE))
import semantic_colleague as semantic
from colleague_availability import availability_context, advance_availability, parse_policy
from harbor_dynamic_colleague_adapter import _transactional_dispatch, SemanticRuntimeState


def item(action, context, private=False):
    fact = context['facts'][0]
    return {'action': action, 'card_ids': [fact['card_id']] if action != 'acknowledge' else [],
            'fact_ids': [fact['fact_id']] if private else [], 'missing_fields': [],
            'redirect_owner': None, 'source_refs': [fact['source_ref']] if private else []}


def answer(context):
    return semantic.TransportResult(json.dumps({
        'items': [item('answer', context, True)],
        'disclosed_fact_ids': [context['facts'][0]['fact_id']],
        'reply': 'Empty input returns an empty list.',
    }), {}, 'completed')


class BudgetTests(unittest.TestCase):
    def responder(self, transport):
        return semantic.SemanticColleagueResponder(base_url='https://invalid.example', api_key='test-only',
            model='fixture', effort='high', timeout_seconds=180, attempts=2, transport=transport)

    def test_exhausted_first_timeout_cannot_reset_whole_decision_budget(self):
        clock = [0.0]
        budgets = []
        context = copy.deepcopy(semantic.CONTEXT_EXAMPLE)
        def transport(**arguments):
            budgets.append(arguments['timeout_seconds'])
            clock[0] += arguments['timeout_seconds']
            raise semantic.SemanticTransportError('request_timeout')
        with patch.object(semantic.time, 'monotonic', side_effect=lambda: clock[0]):
            with self.assertRaises(semantic.SemanticColleagueError):
                self.responder(transport).decide(context)
        self.assertEqual(budgets, [180.0])
        self.assertEqual(clock[0], 180)

    def test_planning_and_answer_share_remaining_whole_decision_budget(self):
        clock = [0.0]
        context = copy.deepcopy(semantic.CONTEXT_EXAMPLE)
        policy = parse_policy({'fixed_followups': True, 'required_followups': 1, 'delay_seconds': 0})
        state = {}
        context['availability'] = availability_context(policy, 'core-01', context['facts'], [], state, 0)
        advance_availability(state, 'core-01', context, [item('defer', context)])
        context['availability'] = availability_context(policy, 'core-01', context['facts'], [], state, 1)
        requests = []
        def transport(**arguments):
            requests.append(arguments)
            clock[0] += 119 if len(requests) == 1 else 20
            return answer(context)
        with patch.object(semantic.time, 'monotonic', side_effect=lambda: clock[0]):
            result = self.responder(transport).decide(context)
        self.assertEqual([request['timeout_seconds'] for request in requests], [180.0, 61.0])
        self.assertEqual([record['phase'] for record in result.phase_records], ['planning', 'answer'])
        self.assertEqual(clock[0], 139)
        self.assertEqual(json.loads(requests[0]['prompt'])['facts'][0]['answer'], semantic.UNAVAILABLE_ANSWER)
        self.assertEqual(json.loads(requests[1]['prompt'])['context']['facts'][0]['answer'], context['facts'][0]['answer'])

    def test_fast_failure_preserves_retry_with_only_the_remaining_budget(self):
        clock = [0.0]
        budgets = []
        context = copy.deepcopy(semantic.CONTEXT_EXAMPLE)
        def transport(**arguments):
            budgets.append(arguments['timeout_seconds'])
            clock[0] += 20
            if len(budgets) == 1:
                raise semantic.SemanticTransportError('request_timeout')
            return answer(context)
        with patch.object(semantic.time, 'monotonic', side_effect=lambda: clock[0]):
            result = self.responder(transport).decide(context)
        self.assertEqual(budgets, [180.0, 160.0])
        self.assertEqual([record['status'] for record in result.phase_records], ['error', 'validated'])
        self.assertEqual(clock[0], 40)

    def test_auth_failure_is_not_retried_or_cached(self):
        calls = []
        def transport(**arguments):
            calls.append(arguments)
            raise semantic.SemanticTransportError('http_403')
        responder = self.responder(transport)
        for attempt in range(2):
            with self.assertRaises(semantic.SemanticColleagueError) as caught:
                responder.decide(copy.deepcopy(semantic.CONTEXT_EXAMPLE))
            self.assertEqual(caught.exception.attempt_count, 1)
            self.assertFalse(caught.exception.retryable)
        self.assertEqual(len(calls), 2)

    def test_out_of_owner_fact_fails_closed(self):
        def transport(**arguments):
            result = json.loads(answer(semantic.CONTEXT_EXAMPLE).text)
            result['items'][0]['fact_ids'] = ['another-owner-fact']
            return semantic.TransportResult(json.dumps(result), {}, 'completed')
        with self.assertRaises(semantic.SemanticColleagueError):
            self.responder(transport).decide(copy.deepcopy(semantic.CONTEXT_EXAMPLE))

    def test_transaction_rollback_preserves_aliases_and_pending_state(self):
        events = []
        runtime = SimpleNamespace(lock=threading.RLock(), messages={'dm': []},
                                  reply_timing_state={'core-01': {'cards': {}}})
        alias = runtime.messages['dm']
        runtime.log = lambda event, **fields: events.append((event, fields))
        def dispatch(request):
            alias.append('must roll back')
            runtime.reply_timing_state['core-01']['cards']['DEMO-1'] = {'qualified_followups': 99}
            runtime.log('colleague_model_failed_closed', error_code='request_timeout')
            raise RuntimeError('provider failed')
        runtime.dispatch = dispatch
        with self.assertRaises(RuntimeError):
            _transactional_dispatch(runtime, {'action': 'send'})
        self.assertIs(runtime.messages['dm'], alias)
        self.assertEqual(alias, [])
        self.assertEqual(runtime.reply_timing_state['core-01']['cards'], {})
        self.assertEqual(events[0][1]['transaction_committed'], False)


class FollowupTests(unittest.TestCase):
    def test_real_runtime_tool_results_follow_relevant_topic_progress(self):
        policy = json.loads((ORIGINAL / 'authoring/colleague_reply_timing.json').read_text())
        for owner, card_id, threshold in [('core-02', 'AUR-223', 2), ('core-04', 'AUR-224', 1)]:
            with self.subTest(card_id=card_id):
                requests = []
                def transport(**arguments):
                    value = json.loads(arguments['prompt'])
                    context = value.get('context', value)
                    requests.append(context)
                    self.assertEqual(context['owner']['id'], owner)
                    fact = next(fact for fact in context['facts'] if fact['card_id'] == card_id)
                    row = next(row for row in context['availability']['cards'] if row['card_id'] == card_id)
                    if context['message'] == 'unrelated greeting':
                        action, disclosed, reply = 'acknowledge', [], 'Hello.'
                    elif row['can_answer']:
                        action, disclosed, reply = 'answer', [fact['fact_id']], fact['answer']
                    else:
                        action, disclosed, reply = 'defer', [], f'I will return to {card_id}; this topic remains pending.'
                    response_item = dict(action=action, card_ids=[] if action == 'acknowledge' else [card_id],
                        fact_ids=disclosed, missing_fields=[], redirect_owner=None,
                        source_refs=[fact['source_ref']] if disclosed else [])
                    if reply == semantic.UNAVAILABLE_ANSWER:
                        reply = 'Planning a response.'
                    return semantic.TransportResult(json.dumps(dict(items=[response_item],
                        disclosed_fact_ids=disclosed, reply=reply)), {}, 'completed')
                responder = semantic.SemanticColleagueResponder(base_url='https://invalid.example', api_key='test-only',
                    model='fixture', effort='high', transport=transport)
                runtime = SemanticRuntimeState(ORIGINAL / 'authoring', semantic_responder=responder,
                    reply_timing_policy=policy, reply_clock=lambda: 1000)
                def send(text):
                    return _transactional_dispatch(runtime, dict(action='send', recipient_id=owner, text=text))
                first = send('relevant request')
                self.assertIn('pending', first['reply']['text'])
                self.assertEqual(runtime.answered_facts[owner], set())
                saved = copy.deepcopy(runtime.reply_timing_state)
                send('unrelated greeting')
                _transactional_dispatch(runtime, dict(action='check_updates', worktree_progress=False))
                self.assertEqual(runtime.reply_timing_state, saved)
                for followup in range(threshold):
                    result = send(f'relevant followup {followup}')
                expected = next(fact['answer'] for fact in runtime.packs[owner]['facts'] if fact['card_id'] == card_id)
                self.assertEqual(result['reply']['text'], expected)
                self.assertEqual(len(runtime.answered_facts[owner]), 1)
                self.assertFalse(runtime.reply_timing_state[owner]['cards'][card_id]['opened_at'] is None)

    def test_fixed_followups_remain_reachable_and_pending_is_not_missing(self):
        policy = parse_policy(json.loads((ORIGINAL / 'authoring/colleague_reply_timing.json').read_text()))
        packs = list((ORIGINAL / 'authoring/orgchat_auto1/knowledge_packs').glob('*.json'))
        for card_id, threshold in [('AUR-223', 2), ('AUR-224', 1)]:
            with self.subTest(card_id=card_id):
                pack = next(json.loads(path.read_text()) for path in packs
                            if any(fact['card_id'] == card_id for fact in json.loads(path.read_text())['facts']))
                fact = next(fact for fact in pack['facts'] if fact['card_id'] == card_id)
                context = copy.deepcopy(semantic.CONTEXT_EXAMPLE)
                context['owner']['id'] = pack['owner']
                context['facts'] = [dict(fact_id=fact['iu'], card_id=card_id, answer=fact['answer'],
                                         module=fact['module'], topic=fact['topic'], source_ref='fact:' + fact['iu'])]
                state = {}
                def refresh(now):
                    context['availability'] = availability_context(policy, pack['owner'], context['facts'], [], state, now)
                    return context['availability']['cards'][0]
                self.assertFalse(refresh(0)['can_answer'])
                advance_availability(state, pack['owner'], context, [item('defer', context)])
                self.assertTrue(refresh(1000)['pending'])
                saved = copy.deepcopy(state)
                advance_availability(state, pack['owner'], context, [item('acknowledge', context)])
                self.assertEqual(state, saved)
                refresh(2000)
                self.assertEqual(state, saved)
                for followup in range(1, threshold + 1):
                    ready = refresh(2000 + followup)['can_answer']
                    self.assertEqual(ready, followup == threshold)
                    action = item('answer', context, True) if ready else item('defer', context)
                    advance_availability(state, pack['owner'], context, [action])
                self.assertFalse(refresh(3000)['pending'])
                self.assertEqual(state[pack['owner']]['cards'][card_id]['qualified_followups'], threshold)


if __name__ == '__main__':
    unittest.main()
