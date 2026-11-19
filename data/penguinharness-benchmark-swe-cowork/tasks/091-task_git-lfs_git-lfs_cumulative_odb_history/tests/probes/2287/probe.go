package odb

import (
	"path/filepath"
	"testing"
)

func TestTaskContractObjectDatabaseRoot(test *testing.T) {
	repo := taskRepo(test)
	expected := filepath.Join(repo.dir, ".git", "objects")
	database, err := FromFilesystem(expected)
	if err != nil {
		test.Fatal(err)
	}
	defer database.Close()
	if root, ok := database.Root(); !ok || root != expected {
		test.Fatalf("root=%q,%v", root, ok)
	}
	memory := FromMemory()
	defer memory.Close()
	if root, ok := memory.Root(); ok || root != "" {
		test.Fatalf("memory root=%q,%v", root, ok)
	}
}
