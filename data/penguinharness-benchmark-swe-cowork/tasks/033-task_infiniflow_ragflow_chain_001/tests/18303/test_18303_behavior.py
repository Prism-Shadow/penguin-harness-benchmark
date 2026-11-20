from integration_support import run_production_case


def test_navigation_graph_text_includes_every_entity_description():
    run_production_case('test_generate_nav_preserves_full_graph')
