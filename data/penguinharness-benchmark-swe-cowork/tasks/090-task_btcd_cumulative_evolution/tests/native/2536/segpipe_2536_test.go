package btcjson

import (
	"encoding/json"
	"testing"
)

func TestSegpipe2536NullWarningsDecodeAsNil(t *testing.T) {
	value := StringOrArray{"stale"}
	if err := json.Unmarshal([]byte("null"), &value); err != nil {
		t.Fatalf("decode null StringOrArray: %v", err)
	}
	if value != nil {
		t.Fatalf("decoded null as %#v, want nil", value)
	}
}

func TestSegpipe2536WarningsPositiveForms(t *testing.T) {
 for _,tc:=range []struct{input string; expected []string}{
 {`"one"`,[]string{"one"}}, {`["one","two"]`,[]string{"one","two"}}, {`[]`,[]string{}},
 } {
  value:=StringOrArray{"stale"}; if err:=json.Unmarshal([]byte(tc.input),&value);err!=nil {t.Fatal(err)}
  if len(value)!=len(tc.expected) {t.Fatalf("%s -> %#v",tc.input,value)}
  for i,want:=range tc.expected {if value[i]!=want {t.Fatalf("%s -> %#v",tc.input,value)}}
 }
 for _,bad:=range []string{`123`,`{}`,`["ok",2]`} {
  var value StringOrArray;if err:=json.Unmarshal([]byte(bad),&value);err==nil {t.Fatalf("accepted %s",bad)}
 }
}
