package git

import "testing"

func TestTaskContractMigrationRefCompatibility(t *testing.T) {
	cases := []struct {
		raw  string
		typ  RefType
		name string
	}{
		{"refs/heads/main", RefTypeLocalBranch, "main"},
		{"refs/tags/v1", RefTypeLocalTag, "v1"},
	}
	for _, tc := range cases {
		typ, name := ParseRefToTypeAndName(tc.raw)
		if typ != tc.typ || name != tc.name {
			t.Fatalf("%s => %d,%q", tc.raw, typ, name)
		}
	}
}
