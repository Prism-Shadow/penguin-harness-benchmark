package taskcontract

import (
    "os"
    "os/exec"
    "path/filepath"
    "strings"
    "testing"
)

type taskRepository struct { dir string; test *testing.T }

func taskRepo(test *testing.T) *taskRepository {
    test.Helper()
    repo := &taskRepository{dir: test.TempDir(), test: test}
    repo.run("init", "-q")
    repo.run("symbolic-ref", "HEAD", "refs/heads/task-main")
    repo.run("config", "user.name", "Task Contract")
    repo.run("config", "user.email", "contract@example.invalid")
    repo.run("config", "commit.gpgsign", "false")
    repo.run("config", "core.autocrlf", "false")
    repo.run("config", "core.hooksPath", filepath.Join(repo.dir, "no-hooks"))
    return repo
}

func (repo *taskRepository) run(args ...string) string {
    repo.test.Helper()
    command := exec.Command("git", args...)
    command.Dir = repo.dir
    command.Env = append(os.Environ(), "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null")
    output, err := command.CombinedOutput()
    if err != nil { repo.test.Fatalf("git %v: %v (%s)", args, err, output) }
    return strings.TrimSpace(string(output))
}

func (repo *taskRepository) write(name, content string) {
    repo.test.Helper()
    path := filepath.Join(repo.dir, name)
    if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil { repo.test.Fatal(err) }
    if err := os.WriteFile(path, []byte(content), 0644); err != nil { repo.test.Fatal(err) }
}

func (repo *taskRepository) commit(message string) string {
    repo.test.Helper()
    repo.run("add", ".")
    repo.run("commit", "--allow-empty", "-q", "-m", message)
    return repo.run("rev-parse", "HEAD")
}
