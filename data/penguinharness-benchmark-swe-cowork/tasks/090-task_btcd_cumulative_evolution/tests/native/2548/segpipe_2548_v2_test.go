package netsync

import (
	"testing"

	"github.com/btcsuite/btcd/chaincfg/v2"
	"github.com/btcsuite/btcd/peer"
	"github.com/btcsuite/btcd/wire/v2"
)

func TestSegpipe2548RegtestRequiresBlockService(t *testing.T) {
	for _, params := range []chaincfg.Params{chaincfg.RegressionNetParams,chaincfg.SimNetParams} {
	manager := &SyncManager{chainParams: &params}

	noServices := peer.NewInboundPeer(&peer.Config{ChainParams: &params})
	if manager.isSyncCandidate(noServices) {
		t.Fatal("regtest peer without block-serving flags was accepted")
	}

	fullNode := peer.NewInboundPeer(&peer.Config{
		ChainParams: &params,
		Services:    wire.SFNodeNetwork,
	})
	if !manager.isSyncCandidate(fullNode) {
		t.Fatal("regtest full node was rejected")
	}
	}
}
