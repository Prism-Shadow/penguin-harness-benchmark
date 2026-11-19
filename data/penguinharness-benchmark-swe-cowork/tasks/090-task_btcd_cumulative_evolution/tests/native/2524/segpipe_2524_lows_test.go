package ecdsa

import (
	"encoding/asn1"
	"math/big"
	"testing"
)

func TestSegpipe2524StrictDERLowS(t *testing.T) {
	order, ok := new(big.Int).SetString("fffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141", 16)
	if !ok { t.Fatal("bad test order") }
	half := new(big.Int).Rsh(new(big.Int).Set(order), 1)
	encode := func(r, s *big.Int) []byte {
		result, err := asn1.Marshal(struct { R, S *big.Int }{r, s})
		if err != nil { t.Fatal(err) }
		return result
	}
	one := big.NewInt(1)
	valid := encode(one, one)
	cases := []struct { name string; encoded []byte; valid bool }{
		{"minimal", valid, true},
		{"half_order", encode(one, half), true},
		{"padded_positive_R", encode(big.NewInt(128), one), true},
		{"above_half", encode(one, new(big.Int).Add(half, one)), false},
		{"order", encode(one, order), false},
		{"zero_S", encode(one, big.NewInt(0)), false},
		{"zero_R", encode(big.NewInt(0), one), false},
		{"negative_R", encode(big.NewInt(-1), one), false},
		{"negative_S", encode(one, big.NewInt(-1)), false},
		{"padded_R", []byte{0x30, 7, 2, 2, 0, 1, 2, 1, 1}, false},
		{"padded_S", []byte{0x30, 7, 2, 1, 1, 2, 2, 0, 1}, false},
		{"truncated", valid[:len(valid)-1], false},
		{"trailing", append(append([]byte{}, valid...), 0), false},
		{"long_form_length", []byte{0x30, 0x81, 6, 2, 1, 1, 2, 1, 1}, false},
		{"empty", nil, false},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			err := VerifyLowS(c.encoded)
			if (err == nil) != c.valid { t.Fatalf("VerifyLowS(%x)=%v, valid=%v", c.encoded, err, c.valid) }
		})
	}
}
