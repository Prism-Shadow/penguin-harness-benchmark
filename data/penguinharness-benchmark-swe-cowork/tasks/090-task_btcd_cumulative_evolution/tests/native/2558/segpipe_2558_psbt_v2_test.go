package psbt

import (
 "bytes"
 "encoding/base64"
 "errors"
 "io"
 "strings"
 "testing"
 "github.com/btcsuite/btcd/wire/v2"
)

func segpipe2558Packet(t *testing.T, field string, suffix bool) []byte {
 t.Helper()
 tx:=wire.NewMsgTx(2);tx.AddTxIn(wire.NewTxIn(&wire.OutPoint{},nil,nil));tx.AddTxOut(wire.NewTxOut(17,[]byte{0x51}))
 var txBytes,outBytes bytes.Buffer
 if err:=tx.Serialize(&txBytes);err!=nil {t.Fatal(err)}
 if err:=wire.WriteTxOut(&outBytes,0,0,tx.TxOut[0]);err!=nil {t.Fatal(err)}
 global:=append([]byte{},txBytes.Bytes()...)
 inputKey:=byte(255);var input []byte
 switch field {
 case "global":if suffix {global=append(global,0)}
 case "non-witness-utxo":inputKey=0;input=append([]byte{},txBytes.Bytes()...)
 case "witness-utxo":inputKey=1;input=append([]byte{},outBytes.Bytes()...)
 }
 if suffix && input!=nil {input=append(input,0)}
 var raw bytes.Buffer;raw.Write([]byte{'p','s','b','t',0xff})
 entry:=func(key byte,value []byte) {
  if err:=wire.WriteVarBytes(&raw,0,[]byte{key});err!=nil {t.Fatal(err)}
  if err:=wire.WriteVarBytes(&raw,0,value);err!=nil {t.Fatal(err)}
 }
 entry(0,global);raw.WriteByte(0)
 if input!=nil {entry(inputKey,input)}
 raw.WriteByte(0);raw.WriteByte(0)
 return raw.Bytes()
}

func TestSegpipe2558EmbeddedPSBTValues(t *testing.T) {
 for _,field:=range []string{"global","non-witness-utxo","witness-utxo"} {t.Run(field,func(t *testing.T){
  packet,err:=NewFromRawBytes(bytes.NewReader(segpipe2558Packet(t,field,false)),false)
  if err!=nil || len(packet.UnsignedTx.TxIn)!=1 || len(packet.Inputs)!=1 {t.Fatalf("valid field: %v",err)}
  if _,err:=NewFromRawBytes(bytes.NewReader(segpipe2558Packet(t,field,true)),false);!errors.Is(err,ErrInvalidPsbtFormat) {t.Fatalf("trailing field error: %v",err)}
 })}
}

func TestSegpipe2558PSBTEnvelopeBoundaries(t *testing.T) {
 raw:=segpipe2558Packet(t,"global",false)
 for _,reader:=range []io.Reader{bytes.NewReader(append(append([]byte{},raw...),0)),bytes.NewBuffer(append(append([]byte{},raw...),0))} {
  if _,err:=NewFromRawBytes(reader,false);!errors.Is(err,ErrInvalidPsbtFormat) {t.Fatalf("raw packet suffix: %v",err)}
 }
 encoded:=base64.StdEncoding.EncodeToString(raw)
 packet,err:=NewFromRawBytes(strings.NewReader(encoded),true)
 if err!=nil || packet.UnsignedTx.TxOut[0].Value!=17 {t.Fatalf("canonical base64: %v",err)}
 cases:=[]string{
  encoded[:4]+"\n"+encoded[4:],encoded[:4]+"\r"+encoded[4:],encoded[:4]+" "+encoded[4:],
  encoded[:4]+"!"+encoded[4:],encoded[:len(encoded)-1],base64.StdEncoding.EncodeToString(append(append([]byte{},raw...),0)),
 }
 for i,text:=range cases {if _,err:=NewFromRawBytes(strings.NewReader(text),true);!errors.Is(err,ErrInvalidPsbtFormat) {t.Fatalf("invalid base64 form %d: %v",i,err)}}
}
