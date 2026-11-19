package odb

import (
	"errors"
	"strings"
	"testing"
)

type taskBlobReader struct {
	*strings.Reader
	closes  int
	failure error
}

func (reader *taskBlobReader) Close() error { reader.closes++; return reader.failure }

func TestTaskContractHistoryBlobCloseBoundary(test *testing.T) {
	expected := errors.New("close boundary")
	source := &taskBlobReader{Reader: strings.NewReader("blob"), failure: expected}
	blob := &Blob{}
	if _, err := blob.Decode(source, 4); err != nil {
		test.Fatal(err)
	}
	if err := blob.Close(); err != expected {
		test.Fatalf("close error=%v", err)
	}
	if source.closes != 1 {
		test.Fatalf("close count=%d", source.closes)
	}
}
