package odb

import (
	"encoding/hex"
	"io"
	"os"
	"path/filepath"
	"testing"
)

func TestTaskContractObjectShardCreation(test *testing.T) {
	repo := taskRepo(test)
	database, err := FromFilesystem(filepath.Join(repo.dir, ".git", "objects"))
	if err != nil {
		test.Fatal(err)
	}
	defer database.Close()
	oid, err := database.WriteBlob(NewBlobFromBytes([]byte("sharded payload")))
	if err != nil {
		test.Fatal(err)
	}
	encoded := hex.EncodeToString(oid)
	if _, err := os.Stat(filepath.Join(repo.dir, ".git", "objects", encoded[:2], encoded[2:])); err != nil {
		test.Fatal(err)
	}
	blob, err := database.Blob(oid)
	if err != nil {
		test.Fatal(err)
	}
	defer blob.Close()
	contents, err := io.ReadAll(blob.Contents)
	if err != nil || string(contents) != "sharded payload" {
		test.Fatalf("contents=%q err=%v", contents, err)
	}
}
