package main

import (
	"path/filepath"
	"testing"
)

func segpipeInitLogging(testingContext *testing.T) {
	testingContext.Helper()
	previous := logRotator
	initLogRotator(filepath.Join(testingContext.TempDir(), "btcd.log"))
	current := logRotator
	testingContext.Cleanup(func() {
		if err := current.Close(); err != nil {
			testingContext.Errorf("close test log rotator: %v", err)
		}
		logRotator = previous
	})
}
