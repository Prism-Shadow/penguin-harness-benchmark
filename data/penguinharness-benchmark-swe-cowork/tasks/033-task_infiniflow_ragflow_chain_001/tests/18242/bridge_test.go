package harness

import (
	"context"
	"fmt"
	"sync"
	"testing"
)

func TestBridgeProductionSearchIsolation(test *testing.T) {
	mode, found := GetMode("low")
	if !found || mode.MaxParallelAgents != 1 {
		test.Fatalf("low mode must remain serial: %+v", mode)
	}
	var workers sync.WaitGroup
	for index := 0; index < 4; index++ {
		workers.Add(1)
		go func(index int) {
			defer workers.Done()
			question := fmt.Sprintf("question-%d", index)
			calls := 0
			search := func(ctx context.Context, query, keywords string) ([]map[string]interface{}, []map[string]interface{}) {
				calls++
				if query != question || keywords != "terms" {
					test.Errorf("request changed: %q %q", query, keywords)
				}
				return []map[string]interface{}{{"chunk_id": question, "content_with_weight": question}}, nil
			}
			result := DirectSearch(context.Background(), search, question, "terms", nil)
			if calls != 1 || result.EmptyResult || len(result.Kbinfos.Chunks) != 1 || result.Kbinfos.Chunks[0]["chunk_id"] != question {
				test.Errorf("unexpected production result: %+v calls=%d", result, calls)
			}
		}(index)
	}
	workers.Wait()
	empty := func(context.Context, string, string) ([]map[string]interface{}, []map[string]interface{}) { return nil, nil }
	result := DirectSearch(context.Background(), empty, "missing", "", nil)
	if !result.EmptyResult || len(result.Kbinfos.Chunks) != 0 {
		test.Fatalf("empty request reused evidence: %+v", result)
	}
}
