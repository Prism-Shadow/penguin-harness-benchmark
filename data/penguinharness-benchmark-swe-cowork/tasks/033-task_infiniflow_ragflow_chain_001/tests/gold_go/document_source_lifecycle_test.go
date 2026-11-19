package document

import (
	"context"
	"errors"
	"fmt"
	"ragflow/internal/dao"
	"ragflow/internal/engine/types"
	"ragflow/internal/entity"
	"testing"
)

type repairSourceIndex struct {
	fakeChatDocEngine
	rows   map[string]map[string]interface{}
	reject bool
}

func (e *repairSourceIndex) ChunkStoreExists(context.Context, string, string) (bool, error) {
	return true, nil
}
func (e *repairSourceIndex) Search(_ context.Context, r *types.SearchRequest) (*types.SearchResult, error) {
	var rows []map[string]interface{}
	for _, row := range e.rows {
		if row["doc_id"] != "doc-1" {
			continue
		}
		rows = append(rows, row)
	}
	return &types.SearchResult{Chunks: rows, Total: int64(len(rows))}, nil
}
func (e *repairSourceIndex) DeleteChunks(_ context.Context, filter map[string]interface{}, _, _ string) (int64, error) {
	if e.reject {
		return 0, errors.New("index rejected source deletion")
	}
	var count int64
	for id, row := range e.rows {
		if doc, ok := filter["doc_id"]; ok && doc != row["doc_id"] {
			continue
		}
		if not, ok := filter["must_not"].(map[string]any); ok {
			// Match Elasticsearch's exists behavior, including explicitly empty
			// values. The production fallback must delete those empty source rows.
			if field, ok := not["exists"].(string); ok {
				if _, exists := row[field]; exists {
					continue
				}
			}
		}
		if ids, ok := filter["id"].([]string); ok {
			match := false
			for _, wanted := range ids {
				if wanted == id {
					match = true
				}
			}
			if !match {
				continue
			}
		}
		delete(e.rows, id)
		count++
	}
	return count, nil
}
func TestRepairReparseDeletesOnlySourceRows(t *testing.T) {
	db := setupServiceTestDB(t)
	pushServiceDB(t, db)
	insertTestKB(t, "kb-1", "tenant-1", 1, 10, 5)
	insertTestDocWithRun(t, "doc-1", "kb-1", string(entity.TaskStatusDone), 10, 5)
	doc, err := dao.NewDocumentDAO().GetByID(t.Context(), db, "doc-1")
	if err != nil {
		t.Fatal(err)
	}
	index := &repairSourceIndex{rows: map[string]map[string]interface{}{}}
	for i, kind := range []string{"source", "empty", "wiki_page", "wiki_map_version"} {
		id := fmt.Sprint(i)
		row := map[string]interface{}{"id": id, "doc_id": "doc-1"}
		if kind != "source" {
			row["compile_kwd"] = kind
		}
		if kind == "empty" {
			row["compile_kwd"] = ""
		}
		index.rows[id] = row
	}
	index.rows["other"] = map[string]interface{}{"id": "other", "doc_id": "doc-2"}
	svc := testDocumentService(t)
	svc.docEngine = index
	if err := svc.clearDocumentParseResults(t.Context(), doc, "tenant-1"); err != nil {
		t.Fatal(err)
	}
	if len(index.rows) != 3 || index.rows["2"] == nil || index.rows["3"] == nil || index.rows["other"] == nil {
		t.Fatalf("source deletion lost compiled generations or retained old chunks: %+v", index.rows)
	}
	if err := svc.clearDocumentParseResults(t.Context(), doc, "tenant-1"); err != nil {
		t.Fatal(err)
	}
	if len(index.rows) != 3 {
		t.Fatalf("retry changed compiled rows: %+v", index.rows)
	}
	index.reject = true
	if err := svc.clearDocumentParseResults(t.Context(), doc, "tenant-1"); err == nil {
		t.Fatal("rejected deletion reported success")
	}
}
