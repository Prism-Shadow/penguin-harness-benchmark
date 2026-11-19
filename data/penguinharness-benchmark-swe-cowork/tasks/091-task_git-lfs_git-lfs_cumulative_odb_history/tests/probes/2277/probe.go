package git

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestTaskContractBridgePlatform(t *testing.T) {
	command := exec.Command("go", "build", "-o", filepath.Join(t.TempDir(), "git-lfs.exe"), "github.com/git-lfs/git-lfs")
	command.Env = append(os.Environ(), "GOOS=windows", "GOARCH=amd64", "CGO_ENABLED=0")
	if out, err := command.CombinedOutput(); err != nil {
		t.Fatalf("Windows production build: %v %s", err, out)
	}
	typ, name := ParseRefToTypeAndName("refs/tags/platform")
	if typ != RefTypeLocalTag || name != "platform" {
		t.Fatalf("ref parse=%d,%q", typ, name)
	}
}
