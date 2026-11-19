package txscript

import "testing"

func TestSegpipe2433AnchorScriptClassification(t *testing.T) {
	anchor := []byte{0x51, 0x02, 0x4e, 0x73}
	class := GetScriptClass(anchor)
	if got := class.String(); got != "anchor" {
		t.Fatalf("GetScriptClass(51024e73)=%q, want anchor", got)
	}
}
