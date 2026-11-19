package git

import "testing"

func TestTaskContractRefPrefix(t *testing.T) {
	cases := map[RefType]string{
		RefTypeLocalBranch: "refs/heads", RefTypeRemoteBranch: "refs/remotes",
		RefTypeLocalTag: "refs/tags", RefTypeRemoteTag: "refs/remotes/tags",
	}
	for typ, want := range cases {
		got, ok := typ.Prefix()
		if !ok || got != want {
			t.Fatalf("prefix(%d)=%q,%v", typ, got, ok)
		}
	}
	if got, ok := RefTypeHEAD.Prefix(); ok || got != "" {
		t.Fatalf("HEAD prefix=%q,%v", got, ok)
	}
	for _, tc := range []struct {
		raw, name string
		typ       RefType
	}{
		{"refs/heads/feature/x", "feature/x", RefTypeLocalBranch},
		{"refs/remotes/origin/x", "origin/x", RefTypeRemoteBranch},
		{"refs/tags/v1", "v1", RefTypeLocalTag},
		{"refs/remotes/tags/origin/v1", "origin/v1", RefTypeRemoteTag},
		{"HEAD", "HEAD", RefTypeHEAD},
	} {
		typ, name := ParseRefToTypeAndName(tc.raw)
		if typ != tc.typ || name != tc.name {
			t.Fatalf("parse %s = %d,%q", tc.raw, typ, name)
		}
	}
}
