package schnorr

import (
	"encoding/hex"
	"errors"
	"testing"

	decred_schnorr "github.com/decred/dcrd/dcrec/secp256k1/v4/schnorr"
)

func TestSegpipe2561RejectsSAtOrAboveGroupOrder(t *testing.T) {
	encoded, err := hex.DecodeString(
		"4e45e16932b8af514961a1d3a1a25fdf3f4f7732e9d624c6c61548ab5fb8cd41" +
			"fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141")
	if err != nil {
		t.Fatalf("decode test signature: %v", err)
	}
	_, err = ParseSignature(encoded)
	if !errors.Is(err, decred_schnorr.ErrSigSTooBig) {
		t.Fatalf("ParseSignature error=%v, want ErrSigSTooBig", err)
	}
}

func TestSegpipe2561SignatureFieldBoundaries(t *testing.T) {
 for _,tc:=range []struct{name,r,s string; bad error}{
 {"valid", "4e45e16932b8af514961a1d3a1a25fdf3f4f7732e9d624c6c61548ab5fb8cd41","fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364140",nil},
 {"r-prime","fffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f","0000000000000000000000000000000000000000000000000000000000000001",decred_schnorr.ErrSigRTooBig},
 {"s-order-plus-one","4e45e16932b8af514961a1d3a1a25fdf3f4f7732e9d624c6c61548ab5fb8cd41","fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364142",decred_schnorr.ErrSigSTooBig},
 } {t.Run(tc.name,func(t *testing.T){
  raw,_:=hex.DecodeString(tc.r+tc.s);sig,err:=ParseSignature(raw)
  if tc.bad!=nil {if !errors.Is(err,tc.bad) {t.Fatalf("error=%v want=%v",err,tc.bad)};return}
  if err!=nil || hex.EncodeToString(sig.Serialize())!=hex.EncodeToString(raw) {t.Fatalf("valid signature roundtrip: %v",err)}
 })}
 for _,n:=range []int{0,63,65} {if _,err:=ParseSignature(make([]byte,n));err==nil {t.Fatalf("accepted length %d",n)}}
}
