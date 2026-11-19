package v2transport

import (
	"errors"
	"io"
	"testing"
)

type segpipe2576Writer struct { count int; failure error }
func (writer segpipe2576Writer) Read([]byte) (int, error) { return 0, io.EOF }
func (writer segpipe2576Writer) Write([]byte) (int, error) { return writer.count, writer.failure }

func TestSegpipe2576WriteBoundaries(testingContext *testing.T) {
	injected := errors.New("writer failure")
	for _, test := range []struct { size, count int; failure, expected error }{
		{0, 0, nil, nil}, {1, 1, nil, nil}, {7, 7, nil, nil},
		{7, 0, nil, io.ErrShortWrite}, {7, 6, nil, io.ErrShortWrite},
		{7, 3, injected, injected},
	} {
		peer := NewPeer()
		peer.UseReadWriter(segpipe2576Writer{test.count, test.failure})
		count, err := peer.Send(make([]byte, test.size))
		if count != test.count || !errors.Is(err, test.expected) {
			testingContext.Fatalf("size=%d got=(%d,%v) want=(%d,%v)", test.size, count, err, test.count, test.expected)
		}
	}
}
