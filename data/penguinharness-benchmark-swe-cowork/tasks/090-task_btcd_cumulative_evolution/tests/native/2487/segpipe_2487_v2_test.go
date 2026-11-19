package netsync

import (
	"testing"

	"github.com/btcsuite/btcd/chaincfg/v2"
	"github.com/btcsuite/btcd/peer"
	"github.com/btcsuite/btcd/wire/v2"
)

func TestSegpipe2487RegtestRemoteCandidate(t *testing.T) {
	params := &chaincfg.RegressionNetParams
	manager := &SyncManager{chainParams: params}
	candidate, err := peer.NewOutboundPeer(
		&peer.Config{
			ChainParams: params,
			Services:    wire.SFNodeNetwork,
		},
		"93.184.216.34:18444",
	)
	if err != nil {
		t.Fatalf("create remote regtest peer: %v", err)
	}
	if !manager.isSyncCandidate(candidate) {
		t.Fatal("remote regtest peer was rejected")
	}
}
