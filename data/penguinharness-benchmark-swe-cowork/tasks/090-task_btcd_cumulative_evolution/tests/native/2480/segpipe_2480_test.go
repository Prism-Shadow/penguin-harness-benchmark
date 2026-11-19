package main

import (
	"testing"
	"time"
)

func TestSegpipe2480VerAckCallbackDoesNotBlock(t *testing.T) {
	sp := newServerPeer(&server{}, false)
	done := make(chan struct{})
	go func() {
		sp.OnVerAck(nil, nil)
		close(done)
	}()

	select {
	case <-done:
	case <-time.After(500 * time.Millisecond):
		t.Fatal("OnVerAck blocked while trying to enqueue peer registration")
	}
}
