package psbt

import (
	"errors"
	"strings"
	"testing"
)

func TestSegpipe2539FindLeafScriptRejectsNilInput(t *testing.T) {
	_, err := FindLeafScript(nil, make([]byte, 32))
	if !errors.Is(err, ErrInvalidPsbtFormat) {
		t.Fatalf("FindLeafScript error=%v, want ErrInvalidPsbtFormat", err)
	}
	if !strings.Contains(err.Error(), "nil PSBT input") {
		t.Fatalf("FindLeafScript error=%q, want nil-input context", err)
	}
}
