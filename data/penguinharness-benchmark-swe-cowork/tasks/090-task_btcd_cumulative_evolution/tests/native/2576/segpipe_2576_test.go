package v2transport

import (
	"errors"
	"io"
	"testing"
)

type segpipe2576ShortReadWriter struct{}

func (segpipe2576ShortReadWriter) Read([]byte) (int, error)  { return 0, io.EOF }
func (segpipe2576ShortReadWriter) Write([]byte) (int, error) { return 1, nil }

func TestSegpipe2576SendReportsShortWrite(t *testing.T) {
	peer := NewPeer()
	peer.UseReadWriter(segpipe2576ShortReadWriter{})
	n, err := peer.Send([]byte{1, 2})
	if n != 1 {
		t.Fatalf("Send wrote %d bytes, want 1", n)
	}
	if !errors.Is(err, io.ErrShortWrite) {
		t.Fatalf("Send error=%v, want io.ErrShortWrite", err)
	}
}
