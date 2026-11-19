package txscript

import (
	"testing"

	"github.com/btcsuite/btcd/wire"
)

func TestSegpipe2485CodeSeparatorInSkippedBranch(t *testing.T) {
	tx := wire.NewMsgTx(1)
	tx.AddTxIn(wire.NewTxIn(&wire.OutPoint{}, nil, nil))
	tx.AddTxOut(wire.NewTxOut(0, nil))
	script := []byte{OP_0, OP_IF, OP_CODESEPARATOR, OP_ENDIF, OP_TRUE}
	vm, err := NewEngine(script, tx, 0, ScriptVerifyConstScriptCode,
		nil, nil, -1, nil)
	if err != nil {
		t.Fatalf("NewEngine: %v", err)
	}
	err = vm.Execute()
	if !IsErrorCode(err, ErrCodeSeparator) {
		t.Fatalf("Execute error=%v, want ErrCodeSeparator", err)
	}
}
