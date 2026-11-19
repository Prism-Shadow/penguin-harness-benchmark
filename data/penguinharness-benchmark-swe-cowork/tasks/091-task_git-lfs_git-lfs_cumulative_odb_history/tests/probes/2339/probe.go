package git

import (
	"bytes"
	"encoding/hex"
	"testing"
)

func TestTaskContractUpdateRefIn(test *testing.T) {
	repo := taskRepo(test)
	other := taskRepo(test)
	otherHead := other.commit("unrelated repository")
	other.run("branch", "task", otherHead)
	ref := &Ref{Name: "task", Type: RefTypeLocalBranch}
	for _, message := range []string{"first update", "second update"} {
		repo.write("data.txt", message)
		target := repo.commit(message)
		targetBytes, err := hex.DecodeString(target)
		if err != nil {
			test.Fatal(err)
		}
		if err := UpdateRefIn(repo.dir, ref, targetBytes, message); err != nil {
			test.Fatal(err)
		}
		if got := repo.run("rev-parse", "refs/heads/task"); got != target {
			test.Fatalf("ref=%q object=%q", got, target)
		}
		if got := repo.run("reflog", "show", "-1", "--format=%gs", "refs/heads/task"); got != message {
			test.Fatalf("reflog=%q message=%q", got, message)
		}
		if got := other.run("rev-parse", "refs/heads/task"); got != otherHead {
			test.Fatalf("unrelated repository changed: %q", got)
		}
	}
	before := repo.run("rev-parse", "refs/heads/task")
	if err := UpdateRefIn(repo.dir, ref, bytes.Repeat([]byte{0xff}, 20), "invalid update"); err == nil {
		test.Fatal("missing target object accepted")
	}
	if got := repo.run("rev-parse", "refs/heads/task"); got != before {
		test.Fatalf("failed update moved ref: %q", got)
	}
}
