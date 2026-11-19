package git

import (
	"strings"
	"testing"
)

func TestTaskContractBridgeMessage(t *testing.T) {
	binary := taskCLI(t)
	repo := taskRepo(t)
	repo.write("plain.txt", "ordinary Git data")
	original := repo.commit("plain")
	remote := taskRepo(t)
	remote.commit("remote")
	repo.run("remote", "add", "origin", remote.dir)
	output, err := taskRunCLI(t, binary, repo.dir, "fetch", "origin", "task-main")
	if err != nil || !strings.Contains(string(output), "Fetching") || !strings.Contains(string(output), "task-main") {
		t.Fatalf("fetch CLI: %v %s", err, output)
	}
	if repo.run("rev-parse", "HEAD") != original || repo.run("status", "--porcelain") != "" {
		t.Fatal("fetch modified local repository")
	}
	typ, name := ParseRefToTypeAndName("refs/heads/message")
	if typ != RefTypeLocalBranch || name != "message" {
		t.Fatalf("ref parse=%d,%q", typ, name)
	}
}
