package git

import (
	"encoding/hex"
	"reflect"
	"testing"
)

func TestTaskContractReverseWorkingDirectory(test *testing.T) {
	repo := taskRepo(test)
	var want []string
	for _, value := range []string{"one", "two", "three"} {
		repo.write("data", value)
		want = append(want, repo.commit(value))
	}
	for _, reverse := range []bool{true, false} {
		scanner, err := NewRevListScanner([]string{"HEAD"}, nil, &ScanRefsOptions{Mode: ScanRefsMode, CommitsOnly: true, Reverse: reverse, WorkingDir: repo.dir})
		if err != nil {
			test.Fatal(err)
		}
		var got []string
		for scanner.Scan() {
			got = append(got, hex.EncodeToString(scanner.OID()))
		}
		scanErr, closeErr := scanner.Err(), scanner.Close()
		if scanErr != nil || closeErr != nil {
			test.Fatalf("scan=%v close=%v", scanErr, closeErr)
		}
		expected := append([]string(nil), want...)
		if !reverse {
			expected[0], expected[2] = expected[2], expected[0]
		}
		if !reflect.DeepEqual(got, expected) {
			test.Fatalf("order=%v want=%v", got, expected)
		}
	}
}
