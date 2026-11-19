package chunker

import (
	"context"
	"strings"
	"testing"
)

// The existing public unbroken-atom test may skip a compressible ASCII input.
// This uses real Invoke and deliberately dense Unicode, without any skip path.
func TestRepairTokenChunkerDenseInputStaysBounded(t *testing.T) {
	const budget = 20
	text := strings.Repeat("龍象東京科学語彙🐉🎯🧭", 200)
	if n := tokenizeStr(text); n <= budget {
		t.Fatalf("fixture must exceed budget: %d", n)
	}
	for _, format := range []string{"text", "json"} {
		t.Run(format, func(t *testing.T) {
			component, err := NewTokenChunker(map[string]any{"delimiter_mode": "token_size", "chunk_token_size": budget})
			if err != nil {
				t.Fatal(err)
			}
			input := map[string]any{"name": "dense.txt", "output_format": format}
			if format == "text" {
				input[format] = text
			} else {
				input[format] = []map[string]any{{"text": text, "doc_type_kwd": "text"}}
			}
			out, err := component.Invoke(context.Background(), nil, input)
			if err != nil {
				t.Fatal(err)
			}
			if out["_ERROR"] != nil {
				t.Fatalf("invalid output: %+v", out)
			}
			chunks, ok := out["chunks"].([]map[string]any)
			if !ok || len(chunks) < 2 {
				t.Fatalf("missing split output: %+v", out)
			}
			var joined strings.Builder
			for _, chunk := range chunks {
				body, ok := chunk["text"].(string)
				if !ok || body == "" {
					t.Fatalf("empty chunk: %+v", chunk)
				}
				if n := tokenizeStr(body); n > budget {
					t.Fatalf("chunk exceeds cap: %d > %d", n, budget)
				}
				joined.WriteString(body)
			}
			if strings.ReplaceAll(joined.String(), "\n", "") != text {
				t.Fatal("source bytes lost or duplicated")
			}
		})
	}
}
