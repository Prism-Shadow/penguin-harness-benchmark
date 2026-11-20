from integration_support import run_production_case

def test_parallel_claims_use_independent_routing():
    run_production_case('test_parallel_claims_use_independent_routing')

def test_routed_search_consumers_accept_scope():
    run_production_case('test_routed_search_consumers_accept_scope')



def test_structured_query_after_document_routing():
    run_production_case('test_structured_query_after_document_routing')
