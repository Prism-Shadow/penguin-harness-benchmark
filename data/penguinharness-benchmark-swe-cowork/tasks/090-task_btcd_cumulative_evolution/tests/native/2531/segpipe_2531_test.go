package ecdsa

import (
	"bytes"
	"crypto/sha256"
	"testing"

	"github.com/btcsuite/btcd/btcec/v2"
)

func TestSegpipe2531ECDSADependencyCompatibility(t *testing.T) {
	privateKey, publicKey := btcec.PrivKeyFromBytes(bytes.Repeat([]byte{0x2a}, 32))
	digest := sha256.Sum256([]byte("segpipe dependency compatibility"))
	signature := Sign(privateKey, digest[:])
	if !signature.Verify(digest[:], publicKey) {
		t.Fatal("signature from upgraded dependency did not verify")
	}

	serialized := signature.Serialize()
	parsed, err := ParseDERSignature(serialized)
	if err != nil {
		t.Fatalf("ParseDERSignature: %v", err)
	}
	if !parsed.Verify(digest[:], publicKey) {
		t.Fatal("DER round-trip changed signature verification")
	}
}
