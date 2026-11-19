package main

import "testing"

func TestSegpipe2532ReleaseCandidateVersion(t *testing.T) {
	const expected = "0.26.0-betarc1"
	if got := version(); got != expected {
		t.Fatalf("version()=%q, want %q", got, expected)
	}
}
