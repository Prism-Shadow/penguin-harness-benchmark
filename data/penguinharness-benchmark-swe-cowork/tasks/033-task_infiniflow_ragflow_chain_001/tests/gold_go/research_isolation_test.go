package harness

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"testing"
	"time"

	"gorm.io/gorm"
	"ragflow/internal/agent/chat"
	"ragflow/internal/service/nav"
)

// Only model/retriever/nav storage I/O are fixtures. The exported orchestrator,
// research sessions, navigation traversal and Pipeline all execute unchanged.
type repairResearchChat struct {
	mu     sync.Mutex
	cycles map[string]int
	routed int
	ready  chan struct{}
}

func (c *repairResearchChat) Invoke(ctx context.Context, _ *gorm.DB, req chat.Request) (*chat.Response, error) {
	system := req.Messages[0].Content
	if strings.Contains(system, "You are a research assistant") {
		name := "Alpha"
		if strings.Contains(system, "Research task: Beta") {
			name = "Beta"
		}
		c.mu.Lock()
		cycle := c.cycles[name]
		c.cycles[name]++
		if cycle == 1 {
			c.routed++
			if c.routed == 2 {
				close(c.ready)
			}
		}
		c.mu.Unlock()
		switch cycle {
		case 0:
			return &chat.Response{Content: fmt.Sprintf(`<tool_call>{"name":"dataset_navigation_by_tree","arguments":{"topic":%q}}</tool_call>`, name)}, nil
		case 1:
			select {
			case <-c.ready:
			case <-ctx.Done():
				return nil, ctx.Err()
			}
			return &chat.Response{Content: fmt.Sprintf(`<tool_call>{"name":"hybrid_search","arguments":{"query":%q}}</tool_call>`, name)}, nil
		default:
			return &chat.Response{Content: fmt.Sprintf(`<tool_call>{"name":"generate_report","arguments":{"report":%q,"grounded":[%q],"is_verified":true,"confidence":0.99}}</tool_call>`, "fact "+name, "fact "+name)}, nil
		}
	}
	if strings.Contains(system, "routing a question") {
		index := 0
		if strings.Contains(req.Messages[1].Content, "Documents (numbered)") && strings.Contains(req.Messages[1].Content, "Question:\nBeta\n") {
			index = 1
		}
		return &chat.Response{Content: fmt.Sprintf(`{"relevant":[%d]}`, index)}, nil
	}
	if strings.Contains(system, "answer-groundedness reviewer") {
		return &chat.Response{Content: `{"claims":[{"claim_id":"a","grounded":true},{"claim_id":"b","grounded":true}]}`}, nil
	}
	return &chat.Response{Content: `{"is_sufficient":true,"confidence":0.99,"missing_info":[],"contradictions":[]}`}, nil
}
func TestRepairParallelResearchKeepsClaimRoutingLocal(t *testing.T) {
	original := chat.GetDefaultInvoker()
	defer chat.SetDefaultInvoker(original)
	inv := &repairResearchChat{cycles: map[string]int{}, ready: make(chan struct{})}
	chat.SetDefaultInvoker(inv)
	ns := &fakeNavSvcHarness{clusters: []nav.NavNode{{Name: "root"}}, children: map[string][]nav.NavNode{"root": {{Name: "Alpha", Type: "doc", DocID: "doc-Alpha"}, {Name: "Beta", Type: "doc", DocID: "doc-Beta"}}}}
	var mu sync.Mutex
	seen := map[string][]string{}
	search := &fakeInvokableTool{name: "hybrid_search", fn: func(_ context.Context, raw string) string {
		var args struct {
			Query string   `json:"query"`
			Scope []string `json:"doc_scope"`
		}
		if err := json.Unmarshal([]byte(raw), &args); err != nil {
			return `{}`
		}
		mu.Lock()
		seen[args.Query] = append([]string(nil), args.Scope...)
		mu.Unlock()
		if len(args.Scope) != 1 {
			return `{"chunks":[]}`
		}
		name := strings.TrimPrefix(args.Scope[0], "doc-")
		return fmt.Sprintf(`{"chunks":[{"chunk_id":%q,"doc_id":%q,"content_with_weight":%q}]}`, "chunk-"+name, args.Scope[0], "fact "+name)
	}}
	runner := newProductionRunnerWithTools(nil, "tenant", []string{"kb"}, search, ns)
	evidence := &Kbinfos{}
	pipeline := NewPipeline(nil, "tenant", []string{"kb"}, runner, evidence, nil)
	mode, _ := GetMode("high")
	mode.MaxOrchestratorCycles = 1
	mode.MaxAgentCycles = 3
	claims := []*ClaimTarget{{ClaimID: "a", Description: "Alpha"}, {ClaimID: "b", Description: "Beta"}}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	AgenticResearch(ctx, nil, pipeline, "Alpha and Beta", claims, mode)
	for _, name := range []string{"Alpha", "Beta"} {
		scope := seen[name]
		if len(scope) != 1 || scope[0] != "doc-"+name {
			t.Fatalf("claim %s retrieved with another branch's scope: %v", name, scope)
		}
	}
	if pipeline.HasRoutedScope() {
		t.Fatal("claim-local navigation leaked into the parent pipeline")
	}
	if len(evidence.Chunks) != 2 {
		t.Fatalf("shared evidence lost a branch: %+v", evidence.Chunks)
	}
	for _, claim := range claims {
		if claim.AgentResult == nil || len(claim.AgentResult.EvidenceIDs) != 1 {
			t.Fatalf("claim lost global evidence IDs: %+v", claim)
		}
	}
}
