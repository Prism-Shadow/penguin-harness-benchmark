package githistory

import (
	"encoding/hex"
	"github.com/git-lfs/git-lfs/git/odb"
	"path/filepath"
	"strings"
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

func TestTaskContractEagerCommitCollection(test *testing.T) {
	repo := taskRepo(test)
	repo.write("one.txt", "one")
	first := repo.commit("first")
	repo.write("two.txt", "two")
	repo.commit("second")
	repo.write("three.txt", "three")
	original := repo.commit("third")
	database := taskHistoryDB(test, repo)
	callbacks := 0
	tip, err := NewRewriter(database).Rewrite(&RewriteOptions{Include: []string{"HEAD"}, BlobFn: func(path string, blob *odb.Blob) (*odb.Blob, error) {
		callbacks++
		if callbacks == 1 {
			repo.run("update-ref", "refs/heads/task-main", first)
		}
		return blob, nil
	}})
	if err != nil {
		test.Fatal(err)
	}
	if callbacks != 3 || hex.EncodeToString(tip) != original {
		test.Fatalf("snapshot callbacks=%d tip=%x", callbacks, tip)
	}
	selected := strings.Fields(repo.run("rev-list", "--reverse", hex.EncodeToString(tip)))
	if len(selected) != 3 || selected[0] != first || selected[2] != original {
		test.Fatalf("selected=%v", selected)
	}
}
