package git

import (
	"testing"
)

func TestTaskContractCommitsOnly(test *testing.T) {
	repo := taskRepo(test)
	repo.write("payload", "one")
	repo.commit("one")
	repo.write("payload", "two")
	repo.commit("two")
	for _, only := range []bool{true, false} {
		scanner, err := NewRevListScanner([]string{"HEAD"}, nil, &ScanRefsOptions{Mode: ScanRefsMode, CommitsOnly: only, WorkingDir: repo.dir})
		if err != nil {
			test.Fatal(err)
		}
		count, names := 0, 0
		for scanner.Scan() {
			count++
			if scanner.Name() != "" {
				names++
			}
		}
		scanErr := scanner.Err()
		closeErr := scanner.Close()
		if scanErr != nil || closeErr != nil {
			test.Fatalf("scan=%v close=%v", scanErr, closeErr)
		}
		if only && (count != 2 || names != 0) {
			test.Fatalf("commits=%d names=%d", count, names)
		}
		if !only && (count <= 2 || names == 0) {
			test.Fatal("objects were omitted")
		}
	}
}
