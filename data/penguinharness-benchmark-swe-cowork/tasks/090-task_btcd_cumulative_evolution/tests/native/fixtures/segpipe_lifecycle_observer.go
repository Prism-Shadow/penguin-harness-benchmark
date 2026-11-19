package netsync

import (
	"sync"
	"github.com/btcsuite/btcd/peer"
)

// These verifier-only tracing probes observe calls to the existing public
// SyncManager entry points. They do not replace any production behavior.
type SegpipeLifecycleEvent struct {
	Action string
	Peer *peer.Peer
}

var segpipeLifecycleTrace struct {
	sync.Mutex
	events []SegpipeLifecycleEvent
}

func SegpipeRecordLifecycle(action string, p *peer.Peer) {
	segpipeLifecycleTrace.Lock()
	defer segpipeLifecycleTrace.Unlock()
	segpipeLifecycleTrace.events = append(segpipeLifecycleTrace.events, SegpipeLifecycleEvent{action, p})
}

func SegpipeTakeLifecycle() []SegpipeLifecycleEvent {
	segpipeLifecycleTrace.Lock()
	defer segpipeLifecycleTrace.Unlock()
	events := segpipeLifecycleTrace.events
	segpipeLifecycleTrace.events = nil
	return events
}
