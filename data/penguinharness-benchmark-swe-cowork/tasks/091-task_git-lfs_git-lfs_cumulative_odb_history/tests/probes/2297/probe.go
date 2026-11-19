package githistory

import (
	"encoding/hex"
	"errors"
	"github.com/git-lfs/git-lfs/git/odb"
	"path/filepath"
	"testing"
)

func taskHistoryDB(test *testing.T, repo *taskRepository) *odb.ObjectDatabase {
	database, err := odb.FromFilesystem(filepath.Join(repo.dir, ".git", "objects"))
	if err != nil {
		test.Fatal(err)
	}
	test.Cleanup(func() {
		if err := database.Close(); err != nil {
			test.Error(err)
		}
	})
	return database
}

func TestTaskContractHistoryTreeCallback(test *testing.T) {
	repo := taskRepo(test)
	repo.write("base.txt", "base")
	original := repo.commit("tree")
	database := taskHistoryDB(test, repo)
	extra, err := database.WriteBlob(odb.NewBlobFromBytes([]byte("extra")))
	if err != nil {
		test.Fatal(err)
	}
	tip, err := NewRewriter(database).Rewrite(&RewriteOptions{Include: []string{"HEAD"}, TreeCallbackFn: func(path string, tree *odb.Tree) (*odb.Tree, error) {
		if path != "/" {
			test.Fatalf("tree path=%q", path)
		}
		tree.Entries = append(tree.Entries, &odb.TreeEntry{Name: "extra.txt", Type: odb.BlobObjectType, Filemode: 0100644, Oid: extra})
		return tree, nil
	}})
	if err != nil {
		test.Fatal(err)
	}
	if repo.run("show", hex.EncodeToString(tip)+":extra.txt") != "extra" {
		test.Fatal("tree callback not persisted")
	}
	expected := errors.New("callback failure")
	_, err = NewRewriter(database).Rewrite(&RewriteOptions{Include: []string{"HEAD"}, TreeCallbackFn: func(path string, tree *odb.Tree) (*odb.Tree, error) { return nil, expected }})
	if err != expected {
		test.Fatalf("callback error=%v", err)
	}
	if repo.run("rev-parse", "HEAD") != original {
		test.Fatal("callback moved ref")
	}
}
