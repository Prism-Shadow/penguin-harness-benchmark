package treap

import (
	"bytes"
	"testing"
)

func TestSegpipe2425ImmutableUpdatesPreserveSnapshots(t *testing.T) {
	empty := NewImmutable()
	first := empty.Put([]byte("alpha"), []byte("one"))
	first = first.Put([]byte("beta"), []byte("two"))
	second := first.Put([]byte("alpha"), []byte("changed"))
	second = second.Put([]byte("gamma"), []byte("three"))

	if empty.Len() != 0 {
		t.Fatalf("empty snapshot length=%d, want 0", empty.Len())
	}
	if got := first.Get([]byte("alpha")); !bytes.Equal(got, []byte("one")) {
		t.Fatalf("first snapshot alpha=%q, want one", got)
	}
	if got := first.Get([]byte("beta")); !bytes.Equal(got, []byte("two")) {
		t.Fatalf("first snapshot beta=%q, want two", got)
	}
	if first.Has([]byte("gamma")) {
		t.Fatal("first snapshot was mutated by a later insert")
	}
	if got := second.Get([]byte("alpha")); !bytes.Equal(got, []byte("changed")) {
		t.Fatalf("second snapshot alpha=%q, want changed", got)
	}
	if got := second.Get([]byte("gamma")); !bytes.Equal(got, []byte("three")) {
		t.Fatalf("second snapshot gamma=%q, want three", got)
	}
}
