package infinity

import (
	"reflect"
	"strings"
	"testing"
)

func TestRepairCompiledFieldsRoundTripExistingSchema(t *testing.T) {
	columns := map[string]bool{"id": true, "compile_kwd": true, "content": true, "docnm": true, "title_kwd": true, "scope_kwd": true, "extra": true, "q_3_vec": true}
	input := map[string]interface{}{"id": "wiki", "compile_kwd": "wiki_page", "content_with_weight": "Moon is a satellite", "title_kwd": "Moon", "scope_kwd": "doc", "kc_kind": "page", "kc_payload": "Markdown", "entity_names_kwd": []string{"Moon"}, "q_3_vec": []float32{1, 0, 0}}
	physical, err := packCompiledFields(transformChunkFields(input, nil), columns)
	if err != nil {
		t.Fatal(err)
	}
	for key := range physical {
		if !columns[key] {
			t.Fatalf("undeclared native column %s", key)
		}
	}
	if physical["title_kwd"] != "Moon" || physical["content"] != input["content_with_weight"] {
		t.Fatalf("lost title/content %+v", physical)
	}
	selected := compiledSelectColumns([]string{"id", "kc_kind", "kc_payload", "q_*_vec", "entity_names_kwd", "title_kwd"}, columns)
	for _, want := range []string{"q_3_vec", "extra", "title_kwd"} {
		found := false
		for _, s := range selected {
			if s == want {
				found = true
			}
		}
		if !found {
			t.Fatalf("projection lost %s: %v", want, selected)
		}
	}
	row := map[string]interface{}{}
	for _, field := range selected {
		row[field] = physical[field]
	}
	if err := restoreCompiledFields([]map[string]interface{}{row}); err != nil {
		t.Fatal(err)
	}
	applyFieldMappings([]map[string]interface{}{row})
	if row["kc_kind"] != "page" || row["kc_payload"] != "Markdown" || !reflect.DeepEqual(row["entity_names_kwd"], []interface{}{"Moon"}) {
		t.Fatalf("roundtrip lost metadata: %+v", row)
	}
	input["q_2_vec"] = []float32{1, 0}
	if _, err = packCompiledFields(transformChunkFields(input, nil), columns); err == nil {
		t.Fatal("mixed embedding dimension silently lost")
	}
}

func TestRepairCompiledProvenanceNativeEncoding(t *testing.T) {
	for _, value := range []interface{}{[]string{"doc1", "doc2"}, []interface{}{"doc1", "doc2"}} {
		row := transformChunkFields(map[string]interface{}{"source_doc_ids": value, "outlinks_kwd": value, "children_kwd": value, "aliases": value}, nil)
		if row["source_doc_ids"] != `["doc1","doc2"]` || row["outlinks_kwd"] != row["source_doc_ids"] {
			t.Fatalf("incorrect native JSON: %+v", row)
		}
		if row["children_kwd"] != "doc1###doc2" || row["aliases"] != row["source_doc_ids"] {
			t.Fatalf("schema list encoding %+v", row)
		}
		applyFieldMappings([]map[string]interface{}{row})
		if !reflect.DeepEqual(row["children_kwd"], []interface{}{"doc1", "doc2"}) || !reflect.DeepEqual(row["source_doc_ids"], []interface{}{"doc1", "doc2"}) {
			t.Fatalf("failed native roundtrip %+v", row)
		}
	}
	filter := equivalentConditionToStr(map[string]interface{}{"source_doc_ids": []string{"doc1", "doc2"}, "compile_kwd": "wiki_page", "available_int": 0})
	if !strings.Contains(filter, `json_contains(source_doc_ids, '"doc1"')`) || !strings.Contains(filter, "compile_kwd='wiki_page'") || !strings.Contains(filter, "available_int=0") {
		t.Fatalf("incorrect native filter: %s", filter)
	}
}
