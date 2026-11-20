import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
import time
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import httpx
import jwt
import pytest



def rest_requests(transport, suffix):
    return [request for request in transport.requests if request.url.path.endswith(suffix)]


def test_node_payload_uses_database_identity(dal_transport):
    from robusta.core.model.nodes import NodeInfo

    dal = dal_transport.create("account-nodes", "cluster-nodes")
    node = NodeInfo(name="node-z", node_creation_time="now", internal_ip="10.0.0.9", external_ip="",
                    taints="", conditions="Ready:True", memory_capacity=1, memory_allocatable=1,
                    memory_allocated=0, cpu_capacity=2, cpu_allocatable=2, cpu_allocated=0,
                    pods_count=0, pods="", node_info={}, resource_version=91)
    dal.publish_nodes([node])
    request = rest_requests(dal_transport, "/Nodes")[0]
    payload = json.loads(request.content)[0]
    assert payload["account_id"] == "account-nodes" and payload["cluster_id"] == "cluster-nodes"
    assert payload["name"] == "node-z" and "resource_version" not in payload
    assert "return=minimal" in request.headers["prefer"]


def test_real_factory_session_and_token_refresh(dal_transport):
    dal = dal_transport.create()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert dal.sink_name == "sink" and dal.persist_events is False
    session = dal.client.auth.get_session()
    assert session.access_token == dal_transport.tokens[-1]
    assert session.refresh_token == "refresh-token"
    dal.client.table("Services").select("*").execute()
    request = rest_requests(dal_transport, "/Services")[-1]
    assert request.headers["authorization"] == "Bearer " + session.access_token
    assert request.extensions["timeout"]["read"] == 60
    dal.client.auth.refresh_session()
    dal.client.table("Services").select("*").execute()
    refreshed = rest_requests(dal_transport, "/Services")[-1]
    assert refreshed.headers["authorization"] == "Bearer " + dal_transport.tokens[-1]
    assert refreshed.headers["authorization"] != request.headers["authorization"]


@pytest.mark.parametrize("account,cluster,count,pods", [("acct-a", "east", 3, 7), ("acct-b", "west", 0, 11)])
def test_real_writes_and_rpc(dal_transport, account, cluster, count, pods):
    from robusta.core.model.services import ServiceInfo

    dal = dal_transport.create(account, cluster)
    dal.persist_services([ServiceInfo(name="api-" + cluster, namespace="prod", service_type="Deployment")])
    writes = rest_requests(dal_transport, "/Services")
    assert len(writes) == 1 and writes[0].method == "POST"
    assert "return=minimal" in writes[0].headers["prefer"]
    payload = json.loads(writes[0].content)
    assert payload[0]["account_id"] == account and payload[0]["cluster"] == cluster
    assert payload[0]["name"] == "api-" + cluster
    dal.publish_cluster_nodes(count, pods)
    rpc = rest_requests(dal_transport, "/rpc/update_cluster_node_count")
    assert len(rpc) == 1
    assert json.loads(rpc[0].content) == {"_account_id": account, "_cluster_id": cluster,
                                        "_node_count": count, "_pod_count": pods}
    for active in (False, True):
        dal.set_cluster_active(active)
        request = rest_requests(dal_transport, "/ClustersStatus")[-1]
        assert request.method == "PATCH"
        assert json.loads(request.content) == {"active": active, "updated_at": "now()"}
        assert dict(request.url.params) == {"account_id": "eq." + account, "cluster_id": "eq." + cluster}


@pytest.mark.parametrize("code,message,should_retry", [
    ("PGRST301", "invalid token", True), ("other", "JWT expired", True),
    ("23505", "duplicate key", False), ("57014", "statement expired", False),
])
def test_real_builder_auth_retry(dal_transport, code, message, should_retry):
    from postgrest.exceptions import APIError

    dal = dal_transport.create()
    query = dal.client.table("Services").select("name")
    dal_transport.responses.extend([(401, {"code": code, "message": message, "details": None, "hint": None}),
                                    (200, [{"name": "retry-result"}])])
    before = len(dal_transport.tokens)
    if should_retry:
        response = query.execute()
        assert response.data == [{"name": "retry-result"}]
        assert response is dal_transport.results[-1]
    else:
        with pytest.raises(APIError):
            query.execute()
    assert len(dal_transport.tokens) - before == int(should_retry)
    requests = rest_requests(dal_transport, "/Services")
    assert len(requests) == 1 + int(should_retry)
    if should_retry:
        assert requests[0].url == requests[1].url and requests[0].content == requests[1].content
        assert requests[1].headers["authorization"] == "Bearer " + dal_transport.tokens[-1]


def test_second_auth_failure_does_not_loop_or_cross_clients(dal_transport):
    from postgrest.exceptions import APIError

    first = dal_transport.create("first", "east")
    second = dal_transport.create("second", "west")
    second_token = second.client.auth.get_session().access_token
    error = {"code": "PGRST301", "message": "JWT expired", "details": None, "hint": None}
    dal_transport.responses.extend([(401, error), (401, error), (200, [])])
    before = len(dal_transport.tokens)
    with pytest.raises(APIError):
        first.client.table("Services").select("*").execute()
    assert len(rest_requests(dal_transport, "/Services")) == 2
    assert len(dal_transport.tokens) == before + 1
    assert second.client.auth.get_session().access_token == second_token


@pytest.mark.parametrize("labels", [["Memory", "CPU"], ["IO", "disk", "IO"], []])
def test_report_metadata_reaches_evidence(labels):
    from prometrix import PrometheusQueryResult
    from robusta.core.reporting.base import Enrichment
    from robusta.core.reporting.blocks import GraphBlock, PrometheusBlock
    from robusta.core.sinks.robusta.dal.model_conversion import ModelConversion

    block = PrometheusBlock(PrometheusQueryResult({"resultType": "matrix", "result": []}), "up", metrics_legends_labels=labels)
    graph = GraphBlock("chart.svg", b"<svg/>", graph_data=block)
    assert graph.filename == "chart.svg" and graph.contents == b"<svg/>"
    evidence = ModelConversion.to_evidence_json("acct", "cluster", "sink", "key", uuid4(), Enrichment([block]))
    rendered = json.loads(evidence["data"])
    assert json.loads(rendered[0]["metadata"]["metrics_legends_labels"]) == labels


@pytest.mark.parametrize("kind,operation,team,expected", [
    ("Pod", "UPDATE", "platform", True), ("Deployment", "delete", "platform", True),
    ("Service", "UPDATE", "platform", False), ("Pod", "create", "platform", False),
    ("Pod", "UPDATE", "other", False),
])
def test_multi_resource_should_fire(kind, operation, team, expected):
    from robusta.core.triggers.multi_resources_trigger import MultiResourceTrigger
    from robusta.integrations.kubernetes.base_triggers import IncomingK8sEventPayload, K8sTriggerEvent
    from robusta.utils.scope import ScopeParams

    event = K8sTriggerEvent(k8s_payload=IncomingK8sEventPayload(
        kind=kind, operation=operation.lower(), clusterUid="cluster", description="changed",
        obj={"metadata": {"name": "api", "namespace": "prod", "labels": {"team": team}}}, oldObj=None))
    trigger = MultiResourceTrigger(resources=["Pod", "Deployment"], operations=["UPDATE", "delete"],
                                   scope=ScopeParams(include=[{"labels": "team=platform"}]))
    assert trigger.should_fire(event, "playbook", {}) is expected
    unrestricted = MultiResourceTrigger(resources=[], operations=[])
    assert unrestricted.should_fire(event, "playbook", {}) is True


@pytest.mark.parametrize("change_spec", [False, True])
def test_filtered_event_keeps_original_and_filtered_state(change_spec):
    from robusta.core.triggers.multi_resources_trigger import MultiResourceTrigger
    from robusta.integrations.kubernetes.base_triggers import IncomingK8sEventPayload, K8sTriggerEvent

    original = {"apiVersion": "v1", "kind": "Pod", "metadata": {"name": "api", "namespace": "prod"},
                "spec": {"containers": [{"name": "api", "image": "app:v1"}]}, "status": {"phase": "Running"}}
    updated = deepcopy(original)
    updated["status"]["phase"] = "Failed"
    if change_spec:
        updated["spec"]["containers"][0]["image"] = "app:v2"
    event = K8sTriggerEvent(k8s_payload=IncomingK8sEventPayload(
        kind="Pod", operation="update", apiVersion="v1", clusterUid="cluster", description="changed",
        obj=updated, oldObj=original))
    trigger = MultiResourceTrigger(resources=["Pod"], operations=["update"],
                                   change_filters={"include": ["spec"], "ignore": ["status"]})
    execution = trigger.build_execution_event(event, {}, {})
    assert trigger.check_change_filters(execution) is change_spec
    assert execution.obj.status.phase == "Failed" and execution.old_obj.status.phase == "Running"
    assert execution.obj_filtered.status is None and execution.old_obj_filtered.status is None
    assert bool(execution.filtered_diffs) is change_spec
    assert execution.obj is not execution.obj_filtered


@pytest.mark.parametrize("namespace,name,hidden", [("dev", "worker", False), ("prod", "api", True)])
def test_graph_options_reach_rendering(monkeypatch, namespace, name, hidden):
    from robusta.core.model.base_params import CustomGraphEnricherParams
    from robusta_playbooks import alerts_integration

    renderer = Mock(return_value="rendered-graph")
    monkeypatch.setattr(alerts_integration, "create_graph_enrichment", renderer)
    alert = SimpleNamespace(alert=SimpleNamespace(startsAt=datetime.now(timezone.utc), labels={"namespace": namespace}),
                            get_alert_subject=lambda: SimpleNamespace(name=name), add_enrichment=Mock())
    params = CustomGraphEnricherParams(promql_query="up", graph_title="$namespace/$name rate", hide_legends=hidden)
    alerts_integration.custom_graph_enricher(alert, params)
    assert renderer.call_args.kwargs["graph_title"] == f"{namespace}/{name} rate"
    assert renderer.call_args.kwargs["hide_legends"] is hidden
    assert alert.add_enrichment.call_args.args[0] == ["rendered-graph"]


@pytest.mark.parametrize("retry,available,expected_queries", [(0, True, 1), (2, True, 2), (0, False, 1), (2, False, 3)])
def test_job_retry_boundaries(monkeypatch, retry, available, expected_queries):
    from robusta.integrations.kubernetes import custom_models

    job = object.__new__(custom_models.RobustaJob)
    pod = SimpleNamespace(name="available")
    events = []

    def get_pods():
        events.append("query")
        return [pod] if available and events.count("query") == expected_queries else []

    job.metadata = SimpleNamespace(name="job")
    job.get_pods = get_pods
    monkeypatch.setattr(custom_models.time, "sleep", lambda wait: events.append(("sleep", wait)))
    if available:
        assert job.get_single_pod(retry=retry, wait=0.25) is pod
    else:
        with pytest.raises(Exception):
            job.get_single_pod(retry=retry, wait=0.25)
    assert events == ["query"] + [(item) for unused in range(expected_queries - 1) for item in (("sleep", 0.25), "query")]


def registry():
    return SimpleNamespace(get_global_config=lambda: {"account_id": "acct", "cluster_name": "cluster", "signing_key": "key"})


@pytest.mark.parametrize("labels", [{"zeta": "last", "alpha": "first"}, {"tier": "web", "team": "ops"}])
def test_webhook_public_delivery(monkeypatch, labels):
    from robusta.core.reporting.base import Finding, FindingSubject
    from robusta.core.sinks.webhook.webhook_sink import WebhookSink
    from robusta.core.sinks.webhook.webhook_sink_params import WebhookSinkConfigWrapper, WebhookSinkParams
    import requests

    post = Mock(return_value=SimpleNamespace(raise_for_status=lambda: None))
    monkeypatch.setattr(requests, "post", post)
    finding = Finding(title="message", description="body", aggregation_key="group", subject=FindingSubject(labels=labels))
    for mode in ("json", "text"):
        params = WebhookSinkParams(name="hook", url="https://hook.invalid", size_limit=100000, format=mode, slack_webhook=mode == "json")
        sink = WebhookSink(WebhookSinkConfigWrapper(webhook_sink=params), registry())
        sink.write_finding(finding, False)
        assert post.call_args.args[0] == params.url
        if mode == "json":
            assert "*labels*: " + ", ".join(f"{key}: {labels[key]}" for key in sorted(labels)) in post.call_args.kwargs["json"]["text"]
        else:
            assert "message" in str(post.call_args.kwargs["data"])
    assert post.call_count == 2


@pytest.mark.parametrize("platform_enabled,investigate_link,visible", [(True, True, True), (True, False, False), (False, True, False)])
def test_slack_switch_reaches_delivery(monkeypatch, platform_enabled, investigate_link, visible):
    from robusta.core.reporting.base import Finding
    from robusta.core.reporting.blocks import LinkProp, LinksBlock
    from robusta.core.sinks.slack.slack_sink import SlackSink
    from robusta.core.sinks.slack.slack_sink_params import SlackSinkConfigWrapper, SlackSinkParams
    from robusta.integrations.slack import sender

    web_client = Mock()
    web_client.chat_postMessage.return_value = {"ts": "123"}
    monkeypatch.setattr(sender, "WebClient", Mock(return_value=web_client))
    monkeypatch.setattr(sender.SlackSender, "verified_api_tokens", set())
    monkeypatch.setattr(sender, "HOLMES_ENABLED", False)
    params = SlackSinkParams(name="slack", slack_channel="alerts", api_key="test-token", investigate_link=investigate_link)
    sink = SlackSink(SlackSinkConfigWrapper(slack_sink=params), registry())
    finding = Finding(title="Delivery title", description="Delivery body", aggregation_key="group")
    runbook_url = "https://runbook.invalid/slack-delivery"
    finding.add_enrichment([LinksBlock(links=[LinkProp(text="Runbook", url=runbook_url)])])
    sink.write_finding(finding, platform_enabled)
    web_client.chat_postMessage.assert_called_once()
    message = web_client.chat_postMessage.call_args.kwargs
    assert message["channel"] == "alerts"
    rendered = json.dumps(message, default=str)
    assert (finding.get_investigate_uri("acct", "cluster") in rendered) is visible
    assert "Delivery title" in rendered and "Delivery body" in rendered
    assert runbook_url in rendered
    sender.SlackSender("test-token", "acct", "cluster", "key")
    assert sender.WebClient.call_count == 2
    assert all(call.kwargs["timeout"] == 90 for call in sender.WebClient.call_args_list)


def test_scope_then_time_and_notification_expiry(monkeypatch):
    from robusta.core.reporting import base
    from robusta.core.reporting.base import Finding, FindingSubject
    from robusta.core.sinks.sink_base import NotificationGroup, NotificationSummary
    from robusta.core.sinks.webhook.webhook_sink import WebhookSink
    from robusta.core.sinks.webhook.webhook_sink_params import WebhookSinkConfigWrapper, WebhookSinkParams
    from robusta.utils.scope import ScopeParams

    monkeypatch.setattr(base, "get_namespace_labels", lambda namespace: {})

    params = WebhookSinkParams(name="hook", url="https://hook.invalid", scope=ScopeParams(include=[{"labels": "team=ops"}]))
    sink = WebhookSink(WebhookSinkConfigWrapper(webhook_sink=params), registry())
    matching = Finding(title="a", aggregation_key="a", subject=FindingSubject(labels={"team": "ops"}))
    rejected = Finding(title="b", aggregation_key="b", subject=FindingSubject(labels={"team": "other"}))
    active = Mock(is_active_now=Mock(return_value=True))
    inactive = Mock(is_active_now=Mock(return_value=False))
    sink.time_slices = [inactive, active]
    assert sink.accepts(rejected) is False
    inactive.is_active_now.assert_not_called()
    active.is_active_now.assert_not_called()
    assert sink.accepts(matching) is True
    sink.time_slices = [inactive]
    assert sink.accepts(matching) is False
    clock = [100.0]
    monkeypatch.setattr(time, "time", lambda: clock[0])
    group = NotificationGroup()
    summary = NotificationSummary()
    assert group.register_notification(30, 2) is False
    clock[0] = 130.0
    assert group.register_notification(30, 2) is True
    summary.register_notification(("a",), False, 30)
    summary.register_notification(("b",), True, 30)
    assert summary.summary_table[("a",)] == [1, 0]
    assert summary.summary_table[("b",)] == [0, 1]
    clock[0] = 161.0
    assert group.register_notification(30, 2) is False
    summary.register_notification(("b",), False, 30)
    assert summary.summary_table[("b",)] == [1, 0] and ("a",) not in summary.summary_table

    from robusta.core.sinks.slack.slack_sink import SlackSink
    from robusta.core.sinks.slack.slack_sink_params import SlackSinkConfigWrapper, SlackSinkParams
    from robusta.integrations.slack import sender

    web_client = Mock()
    web_client.chat_postMessage.return_value = {"ts": "123"}
    monkeypatch.setattr(sender, "WebClient", Mock(return_value=web_client))
    monkeypatch.setattr(sender.SlackSender, "verified_api_tokens", set())
    monkeypatch.setattr(sender, "HOLMES_ENABLED", False)
    slack_params = SlackSinkParams(
        name="slack", slack_channel="alerts", api_key="test-token",
        grouping={"group_by": ["namespace"], "interval": 30,
                  "notification_mode": {"regular": {"ignore_first": 2}}},
    )
    slack_sink = SlackSink(SlackSinkConfigWrapper(slack_sink=slack_params), registry())
    delivered_titles = []
    for timestamp, namespace, should_deliver in [
        (200.0, "alpha", False), (201.0, "beta", False),
        (202.0, "alpha", True), (203.0, "beta", True),
        (233.0, "alpha", False), (234.0, "alpha", True),
        (235.0, "beta", False), (236.0, "beta", True),
    ]:
        clock[0] = timestamp
        title = f"Grouped delivery {namespace} at {timestamp}"
        finding = Finding(
            title=title, description="Grouped body", aggregation_key="group",
            subject=FindingSubject(namespace=namespace),
        )
        slack_sink.write_finding(finding, False)
        if should_deliver:
            delivered_titles.append(title)
        assert web_client.chat_postMessage.call_count == len(delivered_titles), (timestamp, namespace)
        for delivery, expected_title in zip(web_client.chat_postMessage.call_args_list, delivered_titles):
            assert delivery.kwargs["channel"] == "alerts"
            rendered = json.dumps(delivery.kwargs, default=str)
            assert expected_title in rendered and "Grouped body" in rendered
