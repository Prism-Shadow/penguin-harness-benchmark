package git

import (
	"os/exec"
	"testing"
)

func TestTaskContractAllRefsIn(t *testing.T) {
	dir := t.TempDir()
	run := func(args ...string) {
		c := exec.Command("git", args...)
		c.Dir = dir
		if out, err := c.CombinedOutput(); err != nil {
			t.Fatalf("git %v: %v (%s)", args, err, out)
		}
	}
	run("init", "-q")
	run("config", "user.email", "task@example.invalid")
	run("config", "user.name", "Task")
	cfile := exec.Command("sh", "-c", "printf %s ref > file")
	cfile.Dir = dir
	if err := cfile.Run(); err != nil {
		t.Fatal(err)
	}
	c := exec.Command("git", "add", "file")
	c.Dir = dir
	if err := c.Run(); err != nil {
		t.Fatal(err)
	}
	c = exec.Command("git", "commit", "-q", "-m", "ref")
	c.Dir = dir
	if err := c.Run(); err != nil {
		t.Fatal(err)
	}
	run("tag", "v-task")
	refs, err := AllRefsIn(dir)
	if err != nil {
		t.Fatal(err)
	}
	seenBranch, seenTag := false, false
	for _, ref := range refs {
		if ref.Name == "master" || ref.Name == "main" {
			seenBranch = true
		}
		if ref.Name == "v-task" {
			seenTag = true
		}
	}
	if !seenBranch || !seenTag {
		t.Fatalf("refs=%v", refs)
	}
}
