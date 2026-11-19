package knowledge_compile

import (
	"context"
	"errors"
	"fmt"
	"path"
	"ragflow/internal/engine"
	"ragflow/internal/engine/types"
	kc "ragflow/internal/ingestion/component/knowledge_compiler/common"
	"sort"
	"strings"
	"sync"
	"testing"
)

// Only the external index boundary is in memory. Selection and filters are
// enforced so missing fields and wrong storage predicates cannot pass.
type repairIndex struct {
	engine.DocEngine
	mu     sync.Mutex
	rows   map[string]map[string]interface{}
	reject bool
}

func newRepairIndex() *repairIndex { return &repairIndex{rows: map[string]map[string]interface{}{}} }
func repairValues(v interface{}) []string {
	switch x := v.(type) {
	case []string:
		return x
	case []interface{}:
		var out []string
		for _, v := range x {
			out = append(out, fmt.Sprint(v))
		}
		return out
	case nil:
		return nil
	default:
		return []string{fmt.Sprint(x)}
	}
}
func repairMatches(row, filter map[string]interface{}) bool {
	for key, want := range filter {
		ok := false
		for _, v := range repairValues(row[key]) {
			for _, w := range repairValues(want) {
				if v == w {
					ok = true
				}
			}
		}
		if !ok {
			return false
		}
	}
	return true
}
func (e *repairIndex) Search(_ context.Context, r *types.SearchRequest) (*types.SearchResult, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	var rows []map[string]interface{}
	ids := make([]string, 0, len(e.rows))
	for id := range e.rows {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	for _, id := range ids {
		row := e.rows[id]
		if !repairMatches(row, r.Filter) {
			continue
		}
		if len(r.KbIDs) > 0 && !repairMatches(row, map[string]interface{}{"kb_id": r.KbIDs}) {
			continue
		}
		out := map[string]interface{}{}
		for key, v := range row {
			for _, field := range r.SelectFields {
				if match, _ := path.Match(field, key); match {
					out[key] = v
				}
			}
		}
		if len(r.SelectFields) == 0 {
			for k, v := range row {
				out[k] = v
			}
		}
		out["score"] = 1.0
		rows = append(rows, out)
	}
	total := len(rows)
	start := r.Offset
	if start > total {
		start = total
	}
	end := total
	if r.Limit > 0 && start+r.Limit < end {
		end = start + r.Limit
	}
	return &types.SearchResult{Chunks: rows[start:end], Total: int64(total)}, nil
}
func (e *repairIndex) InsertChunks(_ context.Context, rows []map[string]interface{}, _, kb string) ([]string, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if e.reject {
		return nil, errors.New("index rejected write")
	}
	var ids []string
	for _, row := range rows {
		id, _ := row["id"].(string)
		copy := map[string]interface{}{}
		for k, v := range row {
			copy[k] = v
		}
		copy["kb_id"] = kb
		e.rows[id] = copy
		ids = append(ids, id)
	}
	return ids, nil
}
func (e *repairIndex) DeleteChunks(_ context.Context, filter map[string]interface{}, _, kb string) (int64, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	var n int64
	for id, row := range e.rows {
		if row["kb_id"] == kb && repairMatches(row, filter) {
			delete(e.rows, id)
			n++
		}
	}
	return n, nil
}
func (e *repairIndex) UpdateChunks(_ context.Context, filter, update map[string]interface{}, _, kb string) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	for _, row := range e.rows {
		if row["kb_id"] == kb && repairMatches(row, filter) {
			for k, v := range update {
				row[k] = v
			}
		}
	}
	return nil
}
func repairWikiRow(doc, slug, text string) map[string]interface{} {
	return map[string]interface{}{"id": doc + "-" + slug, "doc_id": doc, "kb_id": "kb", "tenant_id": "t", "compile_kwd": "wiki_page", "compilation_template_kind_kwd": "wiki", "compilation_template_ids": []string{"template"}, "available_int": 0, "scope_kwd": "doc", "content_with_weight": text, "slug_kwd": "entity/" + slug, "page_type_kwd": "entity", "title_kwd": slug, "topic_kwd": "orbit", "summary_with_weight": "summary", "entity_names_kwd": []string{slug}, "outlinks_kwd": []string{"entity/earth"}, "source_doc_ids": []string{doc}, "source_chunk_ids": []string{doc + "-chunk"}, "q_3_vec": []float32{1, 0, 0}, "create_timestamp_flt": float64(123)}
}
func TestRepairStorageRoundTripAndScopedRebuild(t *testing.T) {
	ctx := context.Background()
	e := newRepairIndex()
	r := engineReader{eng: e}
	w := engineWriter{eng: e}
	row := repairWikiRow("doc", "moon", "Moon orbits Earth")
	e.InsertChunks(ctx, []map[string]interface{}{row, {"id": "source", "doc_id": "doc", "compile_kwd": "", "content_with_weight": "ordinary source"}}, "ragflow_t", "kb")
	products, err := r.LoadDocProducts(ctx, "t", "kb", "doc")
	if err != nil || len(products) != 1 {
		t.Fatalf("read %v %v", products, err)
	}
	p := products[0]
	if p.Variant != kc.VariantWiki || p.Kind != "wiki" || p.TemplateID != "template" || len(p.Vector) != 3 || p.Meta["title"] != "moon" || p.Meta["page_type"] != "entity" || len(metaStringSlice(p.Meta, "outlinks")) != 1 {
		t.Fatalf("lost product metadata: %+v", p)
	}
	if err = w.WriteMerged(ctx, "t", "kb", products); err != nil {
		t.Fatal(err)
	}
	merged, err := r.LoadMergedWikiPages(ctx, "t", "kb")
	if err != nil || len(merged) != 1 || !merged[0].Merged || len(merged[0].Vector) != 3 || merged[0].Meta["created_at_unix"] != float64(123) {
		t.Fatalf("merged roundtrip %+v %v", merged, err)
	}
	e.InsertChunks(ctx, []map[string]interface{}{{"id": "navigation-leaf", "doc_id": "doc", "compile_kwd": "dataset_nav", "scope_kwd": "doc"}}, "ragflow_t", "kb")
	if err = w.DeleteMergedForVariant(ctx, "t", "kb", nil); err != nil {
		t.Fatal(err)
	}
	if _, ok := e.rows["navigation-leaf"]; ok {
		t.Fatal("rebuild retained stale navigation leaf")
	}
	products, err = r.LoadDocProducts(ctx, "t", "kb", "doc")
	if err != nil || len(products) != 1 {
		t.Fatalf("rebuild deleted document contributions: %d %v", len(products), err)
	}
	e.reject = true
	if err = w.WriteMerged(ctx, "t", "kb", products); err == nil {
		t.Fatal("failed persistence reported success")
	}
}
func TestRepairWikiConsumerLifecycle(t *testing.T) {
	ctx := context.Background()
	e := newRepairIndex()
	s := NewFakeScheduler()
	c := NewConsumer(s, WithReader(engineReader{eng: e}), WithWriter(engineWriter{eng: e}), WithDeduperFactory(func(string) (Deduper, error) { return NewNoopDeduper(), nil }))
	c.contributions = newWikiContributionStore(e)
	apply := func(doc, event string) {
		t.Helper()
		if err := s.PublishVariants(ctx, "t", "kb", doc, event, 0, []string{"wiki"}); err != nil {
			t.Fatal(err)
		}
		claim, ok, err := s.Claim(ctx, "kb")
		if err != nil || !ok {
			t.Fatalf("claim %v %v", ok, err)
		}
		if err = c.processBatch(ctx, "t", "kb", claim.Token, claim.Entries); err != nil {
			t.Fatal(err)
		}
		if _, err = s.Ack(ctx, "kb", claim.Token, claim.Entries); err != nil {
			t.Fatal(err)
		}
	}
	for _, item := range [][3]string{{"a", "moon", "Moon orbits Earth"}, {"b", "earth", "Earth is a planet"}} {
		e.InsertChunks(ctx, []map[string]interface{}{repairWikiRow(item[0], item[1], item[2])}, "ragflow_t", "kb")
		apply(item[0], string(EventTypeCompleted))
	}
	r := engineReader{eng: e}
	pages, err := r.LoadMergedWikiPages(ctx, "t", "kb")
	if err != nil || len(pages) != 2 {
		t.Fatalf("consumer failed to create pages: %+v %v", pages, err)
	}
	graph, _ := e.Search(ctx, &types.SearchRequest{KbIDs: []string{"kb"}, Filter: map[string]interface{}{"compile_kwd": "wiki_relation"}})
	if len(graph.Chunks) != 1 {
		t.Fatalf("expected actual page link, got %+v", graph.Chunks)
	}
	row := repairWikiRow("a", "moon", "Moon has craters")
	row["outlinks_kwd"] = []string{}
	e.InsertChunks(ctx, []map[string]interface{}{row}, "ragflow_t", "kb")
	apply("a", string(EventTypeCompleted))
	pages, _ = r.LoadMergedWikiPages(ctx, "t", "kb")
	for _, p := range pages {
		if p.Meta["title"] == "moon" && (!strings.Contains(p.Content, "craters") || strings.Contains(p.Content, "orbits")) {
			t.Fatalf("stale source survived update: %s", p.Content)
		}
	}
	apply("a", string(EventTypeDeleted))
	pages, _ = r.LoadMergedWikiPages(ctx, "t", "kb")
	if len(pages) != 1 || pages[0].Meta["title"] != "earth" {
		t.Fatalf("delete removed wrong page: %+v", pages)
	}
	apply("b", string(EventTypeDeleted))
	pages, _ = r.LoadMergedWikiPages(ctx, "t", "kb")
	if len(pages) != 0 {
		t.Fatalf("last deletion retained pages: %+v", pages)
	}
	graph, _ = e.Search(ctx, &types.SearchRequest{KbIDs: []string{"kb"}, Filter: map[string]interface{}{"compile_kwd": []string{"wiki_entity", "wiki_relation"}}})
	if len(graph.Chunks) != 0 {
		t.Fatalf("last deletion retained graph: %+v", graph.Chunks)
	}
}
func TestRepairStructureIncrementalContributions(t *testing.T) {
	ctx := context.Background()
	e := newRepairIndex()
	w := engineWriter{eng: e}
	put := func(doc, text string) {
		e.InsertChunks(ctx, []map[string]interface{}{{"id": doc + "-entity", "doc_id": doc, "scope_kwd": "doc", "available_int": 0, "compile_kwd": "hypergraph", "compilation_template_kind_kwd": "knowledge_graph", "compilation_template_ids": []string{"template-" + doc}, "knowledge_graph_kwd": "entity", "name_kwd": "moon", "entity_type_kwd": "body", "mention_count_int": 1, "content_with_weight": fmt.Sprintf(`{"name":"Moon","type":"body","description":%q}`, text), "source_doc_ids": []string{doc}, "source_chunk_ids": []string{doc + "-c"}, "q_3_vec": []float32{1, 0, 0}}}, "ragflow_t", "kb")
	}
	check := func(want []string, absent string) {
		t.Helper()
		res, _ := e.Search(ctx, &types.SearchRequest{KbIDs: []string{"kb"}, Filter: map[string]interface{}{"scope_kwd": "dataset", "knowledge_graph_kwd": "entity"}})
		if len(res.Chunks) != 1 {
			t.Fatalf("structure rows=%+v", res.Chunks)
		}
		content := fmt.Sprint(res.Chunks[0]["content_with_weight"])
		for _, v := range want {
			if !strings.Contains(content, v) {
				t.Fatalf("lost contribution %s: %s", v, content)
			}
		}
		if absent != "" && strings.Contains(content, absent) {
			t.Fatalf("stale description: %s", content)
		}
		if len(repairValues(res.Chunks[0]["source_doc_ids"])) != len(want) || len(repairValues(res.Chunks[0]["compilation_template_ids"])) != len(want) {
			t.Fatalf("provenance %+v", res.Chunks)
		}
	}
	put("a", "first fact")
	if err := w.RebuildStructureForDocs(ctx, "t", "kb", []string{"a"}); err != nil {
		t.Fatal(err)
	}
	put("b", "second fact")
	if err := w.RebuildStructureForDocs(ctx, "t", "kb", []string{"b"}); err != nil {
		t.Fatal(err)
	}
	check([]string{"first fact", "second fact"}, "")
	put("a", "updated fact")
	if err := w.RebuildStructureForDocs(ctx, "t", "kb", []string{"a"}); err != nil {
		t.Fatal(err)
	}
	check([]string{"updated fact", "second fact"}, "first fact")
	if err := w.DeleteDocLevelForDocs(ctx, "t", "kb", []string{"a"}); err != nil {
		t.Fatal(err)
	}
	if err := w.RebuildStructureForDocs(ctx, "t", "kb", []string{"a"}); err != nil {
		t.Fatal(err)
	}
	check([]string{"second fact"}, "updated fact")
	if err := w.DeleteDocLevelForDocs(ctx, "t", "kb", []string{"b"}); err != nil {
		t.Fatal(err)
	}
	if err := w.RebuildStructureForDocs(ctx, "t", "kb", []string{"b"}); err != nil {
		t.Fatal(err)
	}
	res, _ := e.Search(ctx, &types.SearchRequest{KbIDs: []string{"kb"}, Filter: map[string]interface{}{"scope_kwd": "dataset", "knowledge_graph_kwd": "entity"}})
	if len(res.Chunks) != 0 {
		t.Fatalf("last source deletion retained entity: %+v", res.Chunks)
	}
}

type repairFailingEmbedding struct{ mode string }

func (e repairFailingEmbedding) Dimensions() int { return 3 }
func (e repairFailingEmbedding) Encode(_ context.Context, texts []string) ([][]float32, error) {
	switch e.mode {
	case "failure":
		return nil, errors.New("embedding unavailable")
	case "missing":
		return nil, nil
	case "empty":
		return make([][]float32, len(texts)), nil
	}
	out := make([][]float32, len(texts))
	for i := range out {
		out[i] = []float32{0, 1, 0}
	}
	return out, nil
}
func TestRepairWikiMergeRejectsEmbeddingFailure(t *testing.T) {
	ctx := context.Background()
	defer kc.SetDepsResolver(nil)
	for _, mode := range []string{"failure", "missing", "empty", "success"} {
		t.Run(mode, func(t *testing.T) {
			kc.SetDepsResolver(func(string, string, string) (kc.Deps, error) {
				return kc.Deps{Chat: repairEvidenceChat{}, Embed: repairFailingEmbedding{mode: mode}}, nil
			})
			e := newRepairIndex()
			s := NewFakeScheduler()
			c := NewConsumer(s, WithReader(engineReader{eng: e}), WithWriter(engineWriter{eng: e}), WithDeduperFactory(func(string) (Deduper, error) { return NewNoopDeduper(), nil }))
			c.contributions = newWikiContributionStore(e)
			for _, doc := range []string{"a", "b"} {
				row := repairWikiRow(doc, "moon", doc+" fact")
				e.InsertChunks(ctx, []map[string]interface{}{row}, "ragflow_t", "kb")
				s.PublishVariants(ctx, "t", "kb", doc, string(EventTypeCompleted), 0, []string{"wiki"})
			}
			claim, ok, err := s.Claim(ctx, "kb")
			if !ok || err != nil {
				t.Fatalf("claim %v %v", ok, err)
			}
			err = c.processBatch(ctx, "t", "kb", claim.Token, claim.Entries)
			if mode == "success" {
				if err != nil {
					t.Fatal(err)
				}
				pages, _ := (engineReader{eng: e}).LoadMergedWikiPages(ctx, "t", "kb")
				if len(pages) != 1 || len(pages[0].Vector) != 3 || pages[0].Vector[1] != 1 {
					t.Fatalf("merged text not reembedded %+v", pages)
				}
			} else {
				if err == nil {
					t.Fatal("failed embedding reported successful compilation")
				}
				if !strings.Contains(strings.ToLower(err.Error()), "embedding") {
					t.Fatalf("did not reach the embedding failure boundary: %v", err)
				}
				pages, _ := (engineReader{eng: e}).LoadMergedWikiPages(ctx, "t", "kb")
				if len(pages) != 0 {
					t.Fatal("failed embedding published searchable page")
				}
			}
		})
	}
}

func TestRepairReaderRejectsAmbiguousStoredVectors(t *testing.T) {
	e := newRepairIndex()
	ctx := context.Background()
	row := repairWikiRow("doc", "moon", "Moon fact")
	row["q_2_vec"] = []float32{1, 0}
	e.InsertChunks(ctx, []map[string]interface{}{row}, "ragflow_t", "kb")
	if _, err := (engineReader{eng: e}).LoadDocProducts(ctx, "t", "kb", "doc"); err == nil {
		t.Fatal("malformed compiled vector silently discarded")
	}
}

// The external model echoes the selected evidence; production still performs
// grouping, model dispatch, rewrite and re-embedding before publishing.
type repairEvidenceChat struct{}

func (repairEvidenceChat) Chat(_ context.Context, req kc.ChatRequest) (*kc.ChatResponse, error) {
	_, evidence, ok := strings.Cut(req.UserPrompt, "EVIDENCE MARKDOWN:\n")
	if !ok {
		return nil, fmt.Errorf("unexpected rewrite request")
	}
	return &kc.ChatResponse{Content: evidence}, nil
}
