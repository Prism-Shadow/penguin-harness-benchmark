use prost::Message;
use vpnhotspotd::shared::proto::daemon;
use vpnhotspotd::shared::protocol::{
    neighbour_deltas_frame, traffic_counter_lines_frame,
};

#[derive(Clone, PartialEq, Message)]
struct LegacyReplyEnvelope {
    #[prost(message, optional, tag = "1")]
    reply: Option<LegacyReply>,
}

#[derive(Clone, PartialEq, Message)]
struct LegacyReply {
    #[prost(uint64, tag = "1")]
    call_id: u64,
    #[prost(message, optional, tag = "3")]
    traffic_counter_lines: Option<LegacyLines>,
}

#[derive(Clone, PartialEq, Message)]
struct LegacyLines {
    #[prost(string, repeated, tag = "1")]
    lines: Vec<String>,
}

#[derive(Clone, PartialEq, Message)]
struct LegacyEventEnvelope {
    #[prost(message, optional, tag = "2")]
    event: Option<LegacyEvent>,
}

#[derive(Clone, PartialEq, Message)]
struct LegacyEvent {
    #[prost(uint64, tag = "1")]
    call_id: u64,
    #[prost(message, optional, tag = "3")]
    neighbour_deltas: Option<daemon::NeighbourDeltas>,
}

#[test]
fn repair_compatibility_counter_frames() {
    for lines in [Vec::new(), vec!["17 201 ACCEPT all -- wlan7 * 192.0.2.9 0.0.0.0/0".into()]] {
        for call_id in [31, 907] {
            let packet = traffic_counter_lines_frame(call_id, &lines);
            let reply = LegacyReplyEnvelope::decode(packet.as_slice()).unwrap().reply.unwrap();
            assert_eq!(reply.call_id, call_id);
            assert_eq!(reply.traffic_counter_lines.unwrap().lines, lines);
        }
    }
}

#[test]
fn repair_compatibility_neighbour_frames() {
    let removal = daemon::NeighbourDelta {
        delta: Some(daemon::neighbour_delta::Delta::Delete(daemon::NeighbourDelete {
            address: vec![192, 0, 2, 9], dev: "eth8".into(),
        })),
    };
    for deltas in [Vec::new(), vec![removal]] {
        let packet = neighbour_deltas_frame(42, deltas.clone());
        let event = LegacyEventEnvelope::decode(packet.as_slice()).unwrap().event.unwrap();
        assert_eq!(event.call_id, 42);
        assert_eq!(event.neighbour_deltas.unwrap().deltas, deltas);
    }
}
