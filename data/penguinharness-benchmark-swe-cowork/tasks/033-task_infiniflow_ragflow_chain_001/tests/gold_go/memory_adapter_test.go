package service

import (
	"context"
	"errors"
	"reflect"
	"testing"

	"ragflow/internal/agent/runtime"
	"ragflow/internal/common"
	"ragflow/internal/dao"
	enginetypes "ragflow/internal/engine/types"
)

type repairMemoryTransport struct {
	user           string
	filter, params map[string]interface{}
	code           common.ErrorCode
	err            error
}

func (m *repairMemoryTransport) SearchMessage(_ context.Context, user string, filter, params map[string]interface{}) ([]map[string]interface{}, common.ErrorCode, error) {
	m.user, m.filter, m.params = user, filter, params
	return []map[string]interface{}{{"message_id": int64(17), "memory_id": "m1", "content": "remembered evidence"}}, m.code, m.err
}
func TestRepairRegisteredMemoryAdapter(t *testing.T) {
	old := runtime.GetMemoryRetrievalService()
	t.Cleanup(func() { runtime.SetMemoryRetrievalService(old) })
	transport := &repairMemoryTransport{code: common.CodeSuccess}
	runtime.SetMemoryRetrievalService(NewAgentMemoryAdapter(transport))
	weight, threshold := 0.25, 0.4
	req := runtime.RetrievalRequest{Query: "recall", MemoryIDs: []string{"m1"}, TenantID: "tenant", TopN: 3, KeywordsSimilarityWeight: &weight, SimilarityThreshold: threshold, SimilarityThresholdSet: true}
	got, err := runtime.GetMemoryRetrievalService().Search(t.Context(), nil, req)
	if err != nil || len(got) != 1 || got[0].ID != "17" || got[0].DatasetID != "m1" || got[0].Content != "remembered evidence" {
		t.Fatalf("memory result lost: %+v %v", got, err)
	}
	if transport.user != "tenant" || !reflect.DeepEqual(transport.filter["memory_id"], []string{"m1"}) || transport.params["query"] != "recall" || transport.params["top_n"] != 3 || transport.params["keywords_similarity_weight"] != weight || transport.params["similarity_threshold"] != threshold {
		t.Fatalf("memory request lost: %+v", transport)
	}
	transport.code = common.CodeServerError
	if _, err = runtime.GetMemoryRetrievalService().Search(t.Context(), nil, req); err == nil {
		t.Fatal("unsuccessful memory service response accepted")
	}
	transport.code = common.CodeSuccess
	transport.err = errors.New("memory index offline")
	if _, err = runtime.GetMemoryRetrievalService().Search(t.Context(), nil, req); !errors.Is(err, transport.err) {
		t.Fatalf("memory error swallowed: %v", err)
	}
	req.MemoryIDs = nil
	if got, err = runtime.GetMemoryRetrievalService().Search(t.Context(), nil, req); err != nil || len(got) != 0 {
		t.Fatalf("empty memory scope reused evidence: %+v %v", got, err)
	}
}
func TestRepairMemoryAdapterUsesAccessFilteredService(t *testing.T) {
	setupMemoryMessageTestDB(t)
	seedMemoryMessages(t)
	index := &memoryMessageDocEngine{searchResp: &enginetypes.SearchResult{Total: 1, Chunks: []map[string]interface{}{{"message_id": int64(13), "memory_id": "mem-owned", "content": "owned evidence"}}}}
	svc := &MemoryService{memoryDAO: dao.NewMemoryDAO(), docEngine: index}
	adapter := NewAgentMemoryAdapter(svc)
	got, err := adapter.Search(t.Context(), dao.DB, runtime.RetrievalRequest{MemoryIDs: []string{"mem-owned", "mem-other"}, TenantID: "user-1", TopN: 2})
	if err != nil || len(got) != 1 || got[0].Content != "owned evidence" {
		t.Fatalf("memory service integration: %+v %v", got, err)
	}
	if index.searchReq == nil || !reflect.DeepEqual(index.searchReq.Filter["memory_id"], []string{"mem-owned"}) || index.searchReq.Filter["status"] != 1 || index.searchReq.Limit != 2 {
		t.Fatalf("access/status scope lost: %+v", index.searchReq)
	}
}
