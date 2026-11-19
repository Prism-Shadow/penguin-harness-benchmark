package wire

import "testing"

func TestSegpipe2518RejectMessageUsesProtocolPayloadLimit(t *testing.T) {
	msg := NewMsgReject(CmdTx, RejectMalformed, "invalid transaction")
	const protocolLimit = uint32(4_000_000)
	if got := msg.MaxPayloadLength(ProtocolVersion); got != protocolLimit {
		t.Fatalf("MsgReject.MaxPayloadLength=%d, want %d", got, protocolLimit)
	}
}
