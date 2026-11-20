package odb

import (
	"io/ioutil"
	"testing"
)

func TestTaskContractBlobByteConstructor(t *testing.T) {
	blob := NewBlobFromBytes([]byte("bytes"))
	if blob.Size != 5 {
		t.Fatalf("size=%d", blob.Size)
	}
	data, err := ioutil.ReadAll(blob.Contents)
	if err != nil || string(data) != "bytes" {
		t.Fatalf("data=%q err=%v", data, err)
	}
}
