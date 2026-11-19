package git

import (
	"io/ioutil"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestTaskContractCheckout(t *testing.T) {
	dir := t.TempDir()
	gitRun := func(args ...string) {
		c := exec.Command("git", args...)
		c.Dir = dir
		if out, err := c.CombinedOutput(); err != nil {
			t.Fatalf("git %v: %v (%s)", args, err, out)
		}
	}
	gitRun("init", "-q")
	gitRun("config", "user.email", "task@example.invalid")
	gitRun("config", "user.name", "Task")
	path := filepath.Join(dir, "tracked.txt")
	if err := ioutil.WriteFile(path, []byte("first"), 0644); err != nil {
		t.Fatal(err)
	}
	gitRun("add", "tracked.txt")
	gitRun("commit", "-q", "-m", "first")
	if err := ioutil.WriteFile(path, []byte("changed"), 0644); err != nil {
		t.Fatal(err)
	}
	old, _ := os.Getwd()
	defer os.Chdir(old)
	if err := os.Chdir(dir); err != nil {
		t.Fatal(err)
	}
	if err := Checkout("HEAD", []string{"tracked.txt"}, true); err != nil {
		t.Fatalf("checkout: %v", err)
	}
	got, _ := ioutil.ReadFile(path)
	if string(got) != "first" {
		t.Fatalf("content=%q", got)
	}
}
