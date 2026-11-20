import sys
import threading
import unittest
from unittest.mock import patch
from pathlib import Path

SERVICE = Path(__file__).resolve().parents[2] / "environment/workplace-service"
sys.path.insert(0, str(SERVICE))
from harbor_dynamic_colleague_adapter import SemanticRuntimeState, _transactional_dispatch, install_dynamic_colleague
from runtime_daemon import DeterministicReplyResponder, ReplyRender
from workplace_sidecar import OfflineWorkplace
from colleague_availability import advance_availability, availability_context, parse_policy


class FlakyResponder(DeterministicReplyResponder):
    blocked_seed = None

    def render(self, envelope):
        if envelope["allowed_content"] == self.blocked_seed:
            return ReplyRender(text="", mode=self.mode, fallback=True, error_kind="RuntimeError")
        return super().render(envelope)


class NotificationRetryTest(unittest.TestCase):
    def test_total_render_failure_stays_pending_until_retry(self):
        responder = FlakyResponder()
        runtime = SemanticRuntimeState(SERVICE / "original/authoring", responder=responder,
                                       semantic_responder=responder)
        runtime.lock = threading.RLock()
        request = {"action": "check_updates", "modules": [], "worktree_progress": False,
                   "closeout": True, "progress_token": ""}
        original_messages = {key: list(value) for key, value in runtime.messages.items()}
        with patch.object(responder, "render", return_value=ReplyRender(
                text="", mode=responder.mode, fallback=True, error_kind="RuntimeError")):
            failed = _transactional_dispatch(runtime, request)
        self.assertTrue(failed["partial"])
        self.assertEqual(failed["released"], 0)
        self.assertEqual(len(failed["pending_notifications"]), len(runtime.plan["deliveries"]))
        self.assertEqual(runtime.messages, original_messages)
        self.assertFalse(runtime.delivered)
        self.assertFalse(runtime.answered_facts)
        recovered = _transactional_dispatch(runtime, request)
        self.assertFalse(recovered["partial"])
        self.assertEqual(recovered["released"], len(runtime.plan["deliveries"]))
        self.assertFalse(recovered["pending_notifications"])
        self.assertEqual(_transactional_dispatch(runtime, request)["released"], 0)

    def test_fixed_related_followups_remain_pending_until_reachable(self):
        policy = parse_policy({"required_followups": 2, "fixed_followups": True,
                               "delay_seconds": 0, "max_wait_seconds": 0})
        state = {}
        facts = [{"fact_id": "fixture-223", "card_id": "DPT-223"},
                 {"fact_id": "fixture-224", "card_id": "DPT-224"}]

        def context():
            return {"owner": {"id": "fixture-owner"}, "facts": facts,
                    "disclosed_fact_ids": [], "message": "DPT-223 input/output clarification",
                    "availability": availability_context(policy, "fixture-owner", facts, [], state, 10)}

        defer = [{"action": "defer", "card_ids": ["DPT-223"]}]
        advance_availability(state, "fixture-owner", context(), defer)
        pending = context()["availability"]["cards"][0]
        self.assertTrue(pending["pending"])
        self.assertFalse(pending["can_answer"])
        self.assertEqual(pending["qualified_followups"], 0)
        advance_availability(state, "fixture-owner", context(), [])
        advance_availability(state, "fixture-owner", context(),
                             [{"action": "defer", "card_ids": ["DPT-224"]}])
        self.assertEqual(context()["availability"]["cards"][0]["qualified_followups"], 0)
        advance_availability(state, "fixture-owner", context(), defer)
        ready = context()["availability"]["cards"][0]
        self.assertEqual(ready["qualified_followups"], 1)
        self.assertTrue(ready["can_answer"])
        advance_availability(state, "fixture-owner", context(),
                             [{"action": "answer", "card_ids": ["DPT-223"],
                               "fact_ids": ["fixture-223"]}])
        rows = context()["availability"]["cards"]
        self.assertFalse(rows[0]["pending"])
        self.assertEqual(rows[0]["qualified_followups"], 2)
        self.assertTrue(rows[1]["pending"])

    def test_pending_reaches_public_workplace_handler(self):
        responder = FlakyResponder()
        runtime = SemanticRuntimeState(SERVICE / "original/authoring", responder=responder,
                                       semantic_responder=responder)
        runtime.lock = threading.RLock()
        responder.blocked_seed = runtime.plan["deliveries"][0]["text"]

        class TestWorkplace(OfflineWorkplace):
            pass

        install_dynamic_colleague(TestWorkplace)
        with patch("harbor_dynamic_colleague_adapter.build_runtime", return_value=runtime):
            workplace = TestWorkplace(SERVICE / "original")
        response = workplace.handlers["chat_check_updates"]({
            "final_sync": True, "_repository_progress": {"available": True, "has_progress": False}
        })
        self.assertTrue(response["partial"])
        self.assertEqual(response["pending_notifications"][0]["status"], "pending_retry")
        self.assertGreater(response["new_message_count"], 0)
        self.assertEqual(response["new_messages"], response["messages"])

    def test_partial_commit_pending_retry_and_no_duplicate(self):
        responder = FlakyResponder()
        runtime = SemanticRuntimeState(SERVICE / "original/authoring", responder=responder,
                                       semantic_responder=responder)
        runtime.lock = threading.RLock()
        deliveries = sorted(runtime.plan["deliveries"], key=lambda item: (item["progress_wave"], item["id"]))
        blocked = deliveries[3]
        responder.blocked_seed = blocked["text"]
        request = {"action": "check_updates", "modules": [], "worktree_progress": False,
                   "closeout": True, "progress_token": ""}
        result = _transactional_dispatch(runtime, request)
        self.assertTrue(result["partial"])
        self.assertEqual(result["released"], len(deliveries) - 1)
        self.assertEqual(result["pending_notifications"][0]["delivery_id"], blocked["id"])
        self.assertEqual(result["pending_notifications"][0]["status"], "pending_retry")
        self.assertNotIn(blocked["id"], runtime.delivered)
        self.assertFalse(runtime.answered_facts)
        committed_ids = {message["id"] for messages in runtime.messages.values() for message in messages}
        retry = _transactional_dispatch(runtime, request)
        self.assertEqual(retry["released"], 0)
        self.assertEqual({message["id"] for messages in runtime.messages.values() for message in messages}, committed_ids)
        responder.blocked_seed = None
        recovered = _transactional_dispatch(runtime, request)
        self.assertEqual(recovered["released"], 1)
        self.assertFalse(recovered["partial"])
        self.assertEqual(len(runtime.delivered), len(deliveries))
        final = _transactional_dispatch(runtime, request)
        self.assertEqual(final["released"], 0)
        self.assertEqual(len({message["id"] for messages in runtime.messages.values() for message in messages}), len(deliveries))
        self.assertFalse(runtime.answered_facts)


if __name__ == "__main__":
    unittest.main()
