package git

import (
	"encoding/hex"
	"testing"
)

func TestTaskContractIncludeExcludeRevisionSets(test *testing.T) {
	repo := taskRepo(test)
	repo.write("data", "boundary")
	boundary := repo.commit("boundary")
	repo.write("data", "selected")
	tip := repo.commit("selected")
	scanner, err := NewRevListScanner([]string{"HEAD"}, []string{boundary}, &ScanRefsOptions{Mode: ScanRefsMode, CommitsOnly: true, WorkingDir: repo.dir})
	if err != nil {
		test.Fatal(err)
	}
	if !scanner.Scan() || hex.EncodeToString(scanner.OID()) != tip || scanner.Scan() {
		test.Fatal("wrong selected revision set")
	}
	scanErr, closeErr := scanner.Err(), scanner.Close()
	if scanErr != nil || closeErr != nil {
		test.Fatalf("scan=%v close=%v", scanErr, closeErr)
	}
	bad, err := NewRevListScanner([]string{"refs/heads/does-not-exist"}, nil, &ScanRefsOptions{Mode: ScanRefsMode, WorkingDir: repo.dir})
	if err == nil {
		for bad.Scan() {
		}
		scanErr, closeErr = bad.Err(), bad.Close()
		if scanErr == nil && closeErr == nil {
			test.Fatal("invalid revision silently accepted")
		}
	}
}
