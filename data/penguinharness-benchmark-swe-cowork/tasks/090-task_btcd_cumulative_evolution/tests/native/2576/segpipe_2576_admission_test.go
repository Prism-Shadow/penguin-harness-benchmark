package connmgr

import (
	"errors"
	"io"
	"net"
	"sync"
	"testing"
	"time"
)

type segpipe2576Listener struct {
	connections chan net.Conn
	closed chan struct{}
	once sync.Once
}

func (listener *segpipe2576Listener) Accept() (net.Conn, error) {
	select {
	case connection := <-listener.connections:
		return connection, nil
	case <-listener.closed:
		return nil, net.ErrClosed
	}
}

func (listener *segpipe2576Listener) Close() error {
	listener.once.Do(func() { close(listener.closed) })
	return nil
}

func (listener *segpipe2576Listener) Addr() net.Addr {
	return &net.TCPAddr{IP: net.IPv4(127, 0, 0, 1), Port: 19090}
}

func segpipe2576Manager(testingContext *testing.T, limit *uint32, callback func(net.Conn)) *segpipe2576Listener {
	testingContext.Helper()
	listener := &segpipe2576Listener{connections: make(chan net.Conn), closed: make(chan struct{})}
	manager, err := New(&Config{
		Listeners: []net.Listener{listener}, OnAccept: callback, MaxInbound: limit,
		Dial: func(net.Addr) (net.Conn, error) { return nil, errors.New("no outbound dial expected") },
	})
	if err != nil { testingContext.Fatal(err) }
	manager.Start()
	testingContext.Cleanup(func() { manager.Stop(); manager.Wait() })
	return listener
}

func segpipe2576Connect(testingContext *testing.T, listener *segpipe2576Listener) net.Conn {
	testingContext.Helper()
	server, client := net.Pipe()
	testingContext.Cleanup(func() { server.Close(); client.Close() })
	select {
	case listener.connections <- server:
	case <-time.After(2 * time.Second): testingContext.Fatal("listener stopped accepting")
	}
	return client
}

func segpipe2576Accepted(testingContext *testing.T, accepted <-chan net.Conn) net.Conn {
	testingContext.Helper()
	select {
	case connection := <-accepted: return connection
	case <-time.After(2 * time.Second): testingContext.Fatal("admission callback missing")
	}
	return nil
}

func segpipe2576Rejected(testingContext *testing.T, client net.Conn) {
	testingContext.Helper()
	client.SetReadDeadline(time.Now().Add(2 * time.Second))
	var payload [1]byte
	if _, err := client.Read(payload[:]); !errors.Is(err, io.EOF) {
		testingContext.Fatalf("saturated connection was not closed: %v", err)
	}
}

func TestSegpipe2576ListenerLifetime(testingContext *testing.T) {
	limit := uint32(1)
	accepted := make(chan net.Conn, 8)
	listener := segpipe2576Manager(testingContext, &limit, func(connection net.Conn) { accepted <- connection })
	segpipe2576Connect(testingContext, listener)
	first := segpipe2576Accepted(testingContext, accepted)
	segpipe2576Rejected(testingContext, segpipe2576Connect(testingContext, listener))
	select { case <-accepted: testingContext.Fatal("saturated callback invoked"); default: }
	var closers sync.WaitGroup
	for attempt := 0; attempt < 16; attempt++ {
		closers.Add(1)
		go func() { defer closers.Done(); first.Close() }()
	}
	closed := make(chan struct{})
	go func() { closers.Wait(); close(closed) }()
	select { case <-closed: case <-time.After(2*time.Second): testingContext.Fatal("repeated Close blocked") }
	segpipe2576Connect(testingContext, listener)
	second := segpipe2576Accepted(testingContext, accepted)
	first.Close()
	segpipe2576Rejected(testingContext, segpipe2576Connect(testingContext, listener))
	second.Close()
	segpipe2576Connect(testingContext, listener)
	segpipe2576Accepted(testingContext, accepted).Close()
}

func TestSegpipe2576HandshakeFailureReleases(testingContext *testing.T) {
	limit := uint32(1)
	entered := make(chan struct{}, 1)
	finished := make(chan struct{}, 1)
	listener := segpipe2576Manager(testingContext, &limit, func(connection net.Conn) {
		entered <- struct{}{}
		var payload [1]byte
		connection.Read(payload[:])
		connection.Close()
		finished <- struct{}{}
	})
	for attempt := 0; attempt < 3; attempt++ {
		client := segpipe2576Connect(testingContext, listener)
		select { case <-entered: case <-time.After(2*time.Second): testingContext.Fatal("handshake not admitted") }
		segpipe2576Rejected(testingContext, segpipe2576Connect(testingContext, listener))
		client.Close()
		select { case <-finished: case <-time.After(2*time.Second): testingContext.Fatal("failed handshake did not close") }
	}
}

func TestSegpipe2576ZeroAndUnlimited(testingContext *testing.T) {
	zero := uint32(0)
	unexpected := make(chan net.Conn, 2)
	disabled := segpipe2576Manager(testingContext, &zero, func(connection net.Conn) { unexpected <- connection })
	segpipe2576Rejected(testingContext, segpipe2576Connect(testingContext, disabled))
	select { case connection := <-unexpected: connection.Close(); testingContext.Fatal("zero budget admitted connection"); default: }
	accepted := make(chan net.Conn, 12)
	unlimited := segpipe2576Manager(testingContext, nil, func(connection net.Conn) { accepted <- connection })
	var held []net.Conn
	for attempt := 0; attempt < 12; attempt++ {
		segpipe2576Connect(testingContext, unlimited)
		held = append(held, segpipe2576Accepted(testingContext, accepted))
	}
	for _, connection := range held { connection.Close() }
}

func TestSegpipe2576ContendingAccepts(testingContext *testing.T) {
	limit := uint32(4)
	accepted := make(chan net.Conn, 24)
	listener := segpipe2576Manager(testingContext, &limit, func(connection net.Conn) { accepted <- connection })
	var submissions sync.WaitGroup
	clients := make([]net.Conn, 24)
	for index := range clients {
		server, client := net.Pipe()
		clients[index] = client
		submissions.Add(1)
		go func() { defer submissions.Done(); listener.connections <- server }()
	}
	submissions.Wait()
	var held []net.Conn
	for count := uint32(0); count < limit; count++ { held = append(held, segpipe2576Accepted(testingContext, accepted)) }
	segpipe2576Rejected(testingContext, segpipe2576Connect(testingContext, listener))
	for _, connection := range held { connection.Close() }
	for _, client := range clients { segpipe2576Rejected(testingContext, client); client.Close() }
	select { case connection := <-accepted: connection.Close(); testingContext.Fatal("concurrent admission exceeded budget"); default: }
	segpipe2576Connect(testingContext, listener)
	segpipe2576Accepted(testingContext, accepted).Close()
}
