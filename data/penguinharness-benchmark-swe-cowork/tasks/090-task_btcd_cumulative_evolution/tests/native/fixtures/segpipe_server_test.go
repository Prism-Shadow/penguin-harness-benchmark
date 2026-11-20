package main

import (
	"errors"
	"io"
	"net"
	"path/filepath"
	"syscall"
	"testing"
	"time"

	"github.com/btcsuite/btcd/chaincfg/v2"
	"github.com/btcsuite/btcd/database"
	_ "github.com/btcsuite/btcd/database/ffldb"
	"github.com/btcsuite/btcd/wire/v2"
)

func segpipeStartServer(testingContext *testing.T, capacity int) (*server, string) {
	return segpipeStartServerPolicy(testingContext, capacity, nil)
}

func segpipeStartServerPolicy(testingContext *testing.T, capacity int, blacklist []string) (*server, string) {
	testingContext.Helper()
	segpipeInitLogging(testingContext)
	previousConfig, previousNetwork := cfg, activeNetParams
	testingContext.Cleanup(func() { cfg, activeNetParams = previousConfig, previousNetwork })
	activeNetParams = &regressionNetParams
	directory := testingContext.TempDir()
	cfg = &config{MaxPeers: capacity + 1, DataDir: directory, RegressionTest: true,
		ConnectPeers: []string{"127.0.0.1:1"}, DisableDNSSeed: true, DisableRPC: true,
		NoCFilters: true, DisableBanning: true, UtxoCacheMaxSizeMiB: 1,
		dial: func(string, string, time.Duration) (net.Conn, error) { return nil, errors.New("test disables outbound") },
		lookup: func(string) ([]net.IP, error) { return nil, errors.New("test disables DNS") }}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil { testingContext.Fatal(err) }
	address := listener.Addr().String()
	if err := listener.Close(); err != nil { testingContext.Fatal(err) }
	params := chaincfg.RegressionNetParams
	db, err := database.Create("ffldb", filepath.Join(directory, "blocks"), params.Net)
	if err != nil { testingContext.Fatal(err) }
	testingContext.Cleanup(func() { if err := db.Close(); err != nil { testingContext.Error(err) } })
	node, err := newServer([]string{address}, blacklist, nil, db, &params, make(chan struct{}))
	if err != nil { testingContext.Fatal(err) }
	node.Start()
	testingContext.Cleanup(func() {
		node.Stop()
		stopped := make(chan struct{})
		go func() { node.WaitForShutdown(); close(stopped) }()
		select {
		case <-stopped:
		case <-time.After(5 * time.Second): testingContext.Error("production server shutdown timed out")
		}
	})
	return node, address
}

func segpipeDial(testingContext *testing.T, address string) net.Conn {
	testingContext.Helper()
	connection, err := net.DialTimeout("tcp", address, 5*time.Second)
	if err != nil { testingContext.Fatal(err) }
	testingContext.Cleanup(func() { connection.Close() })
	return connection
}

func segpipeWrite(testingContext *testing.T, connection net.Conn, message wire.Message) {
	testingContext.Helper()
	if err := connection.SetWriteDeadline(time.Now().Add(5*time.Second)); err != nil { testingContext.Fatal(err) }
	if err := wire.WriteMessage(connection, message, wire.ProtocolVersion, wire.TestNet); err != nil { testingContext.Fatal(err) }
}

func segpipeReadUntil(testingContext *testing.T, connection net.Conn, command string) wire.Message {
	testingContext.Helper()
	return segpipeReadObserved(testingContext, connection, command, nil)
}

func segpipeReadObserved(testingContext *testing.T, connection net.Conn, command string, observe func(wire.Message) bool) wire.Message {
	testingContext.Helper()
	if err := connection.SetReadDeadline(time.Now().Add(5*time.Second)); err != nil { testingContext.Fatal(err) }
	for {
		message, _, err := wire.ReadMessage(connection, wire.ProtocolVersion, wire.TestNet)
		if err != nil { testingContext.Fatalf("waiting for %s: %v", command, err) }
		if message.Command() == command { return message }
		if observe != nil && observe(message) { continue }
		switch message.(type) {
		case *wire.MsgSendAddrV2, *wire.MsgSendHeaders, *wire.MsgGetAddr, *wire.MsgFeeFilter:
		case *wire.MsgPing:
			segpipeWrite(testingContext, connection, wire.NewMsgPong(message.(*wire.MsgPing).Nonce))
		default:
			testingContext.Fatalf("unexpected %s while waiting for %s", message.Command(), command)
		}
	}
}

func segpipeHandshake(testingContext *testing.T, address string, height int32, nonce uint64) net.Conn {
	testingContext.Helper()
	connection := segpipeDial(testingContext, address)
	services := wire.SFNodeNetwork | wire.SFNodeWitness
	localAddress := wire.NewNetAddress(connection.LocalAddr().(*net.TCPAddr), services)
	remoteAddress := wire.NewNetAddress(connection.RemoteAddr().(*net.TCPAddr), services)
	version := wire.NewMsgVersion(localAddress, remoteAddress, nonce, height)
	version.Services = services
	version.DisableRelayTx = true
	segpipeWrite(testingContext, connection, version)
	segpipeReadUntil(testingContext, connection, wire.CmdVersion)
	segpipeWrite(testingContext, connection, wire.NewMsgVerAck())
	segpipeReadUntil(testingContext, connection, wire.CmdVerAck)
	return connection
}

func segpipePing(testingContext *testing.T, connection net.Conn, nonce uint64) {
	testingContext.Helper()
	segpipeWrite(testingContext, connection, wire.NewMsgPing(nonce))
	// Admission is independent of synchronization policy.  A real node may
	// ask this peer for headers or inventory before replying to a ping.  Act
	// as an empty remote chain, retaining the reader's single total deadline.
	message := segpipeReadObserved(testingContext, connection, wire.CmdPong,
		func(message wire.Message) bool {
			switch request := message.(type) {
			case *wire.MsgInv, *wire.MsgHeaders, *wire.MsgNotFound, *wire.MsgAddr, *wire.MsgAddrV2:
				// Valid asynchronous announcements do not decide admission.
			case *wire.MsgGetHeaders:
				segpipeWrite(testingContext, connection, wire.NewMsgHeaders())
			case *wire.MsgGetBlocks:
				segpipeWrite(testingContext, connection, wire.NewMsgInv())
			case *wire.MsgGetData:
				response := wire.NewMsgNotFound()
				for _, item := range request.InvList {
					if err := response.AddInvVect(item); err != nil { testingContext.Fatal(err) }
				}
				segpipeWrite(testingContext, connection, response)
			default:
				return false
			}
			return true
		}).(*wire.MsgPong)
	if message.Nonce != nonce { testingContext.Fatalf("pong nonce %d, want %d", message.Nonce, nonce) }
}

func segpipePeerCount(testingContext *testing.T, node *server, count int32) {
	testingContext.Helper()
	deadline := time.Now().Add(5*time.Second)
	for node.ConnectedCount() != count {
		if time.Now().After(deadline) { testingContext.Fatalf("peer count did not become %d", count) }
		time.Sleep(time.Millisecond)
	}
}

func segpipeRejected(testingContext *testing.T, connection net.Conn) {
	testingContext.Helper()
	if err := connection.SetReadDeadline(time.Now().Add(5*time.Second)); err != nil { testingContext.Fatal(err) }
	var payload [1]byte
	count, err := connection.Read(payload[:])
	if count != 0 || !errors.Is(err, io.EOF) { testingContext.Fatalf("expected admission close, got %d bytes, %v", count, err) }
}

func segpipeHandshakeFailure(testingContext *testing.T, connection net.Conn) {
	testingContext.Helper()
	if err := connection.SetReadDeadline(time.Now().Add(5*time.Second)); err != nil { testingContext.Fatal(err) }
	for {
		message, _, err := wire.ReadMessage(connection, wire.ProtocolVersion, wire.TestNet)
		if errors.Is(err, io.EOF) || errors.Is(err, syscall.ECONNRESET) { return }
		if err != nil { testingContext.Fatalf("failed handshake did not disconnect: %v", err) }
		if _, rejected := message.(*wire.MsgReject); !rejected { testingContext.Fatalf("malformed handshake accepted: %s", message.Command()) }
	}
}
