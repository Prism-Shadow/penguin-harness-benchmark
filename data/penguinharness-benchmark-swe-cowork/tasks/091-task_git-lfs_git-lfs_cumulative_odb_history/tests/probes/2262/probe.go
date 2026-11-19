package git

import (
	"strings"
	"testing"
)

func TestTaskContractBridgeToolchain(t *testing.T) {
	binary := taskCLI(t)
	output, err := taskRunCLI(t, binary, t.TempDir(), "version")
	if err != nil || !strings.Contains(string(output), "git-lfs/") {
		t.Fatalf("built CLI version: %v %s", err, output)
	}
	typ, name := ParseRefToTypeAndName("refs/heads/bridge")
	if typ != RefTypeLocalBranch || name != "bridge" {
		t.Fatalf("ref parse=%d,%q", typ, name)
	}
}
