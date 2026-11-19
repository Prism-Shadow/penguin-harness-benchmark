from types import SimpleNamespace


def test_workflow_context_detection_uses_orquesta_marker():
    from st2common.services import workflows

    assert workflows.is_action_execution_under_workflow_context(
        SimpleNamespace(context={'orquesta': {'task_execution_id': 't1'}})
    ) is True
    assert workflows.is_action_execution_under_workflow_context(
        SimpleNamespace(context={'parent': {'execution_id': 'root'}})
    ) is False
