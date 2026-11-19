package errors_test

import (
	"errors"
	lfsErrors "github.com/git-lfs/git-lfs/errors"
	"net/url"
	"testing"
)

type temporaryTaskFailure struct{}

func (temporaryTaskFailure) Error() string   { return "temporary" }
func (temporaryTaskFailure) Temporary() bool { return true }

func TestTaskContractRetryableURLError(t *testing.T) {
	permanent := &url.Error{Op: "GET", URL: "https://example.invalid", Err: errors.New("permanent")}
	if lfsErrors.IsRetriableError(permanent) {
		t.Fatal("permanent URL error was retryable")
	}
	err := &url.Error{Op: "GET", URL: "https://example.invalid", Err: temporaryTaskFailure{}}
	if !lfsErrors.IsRetriableError(err) {
		t.Fatalf("temporary URL error was not retryable")
	}
}
