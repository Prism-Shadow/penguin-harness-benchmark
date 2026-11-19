package treap

import (
	"bytes"
	"testing"
)

func TestSegpipe2425ImmutableUpdatesPreserveSnapshots(t *testing.T) {
	empty := NewImmutable()
	first := empty.Put(
		KVPair{Key: []byte("alpha"), Value: []byte("one")},
		KVPair{Key: []byte("beta"), Value: []byte("two")},
	)
	second := first.Put(
		KVPair{Key: []byte("alpha"), Value: []byte("changed")},
		KVPair{Key: []byte("gamma"), Value: []byte("three")},
	)

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
		t.Fatal("first snapshot was mutated by a later batch")
	}
	if got := second.Get([]byte("alpha")); !bytes.Equal(got, []byte("changed")) {
		t.Fatalf("second snapshot alpha=%q, want changed", got)
	}
	if got := second.Get([]byte("gamma")); !bytes.Equal(got, []byte("three")) {
		t.Fatalf("second snapshot gamma=%q, want three", got)
	}
}
