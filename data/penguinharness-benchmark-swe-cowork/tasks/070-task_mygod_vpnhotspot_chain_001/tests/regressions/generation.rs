#[test]
fn benchmark_node_78253b84_generation_rechecks() {
    let mut tracker = UpstreamTracker::default();
    let mut config = benchmark_generation_config();
    assert!(tracker.update_session(1, &config));
    assert!(!tracker.update_session(1, &config));
    config.upstream_generation = 2;
    assert!(!tracker.update_session(1, &config));
    config.upstream_generation = 9;
    assert!(!tracker.update_session(1, &config));
    assert!(tracker.finish_probe());
    assert!(!tracker.update_session(1, &config));
    assert!(!tracker.finish_probe());
    config.upstream_generation = 10;
    assert!(tracker.update_session(1, &config));
    config.upstream_generation = 11;
    assert!(!tracker.update_session(1, &config));
    tracker.remove_session(1);
    assert!(!tracker.finish_probe());
    assert!(tracker.update_session(2, &config));
    config.primary_upstream_interfaces = vec!["ipsec7".into()];
    assert!(!tracker.update_session(2, &config));
    assert!(tracker.finish_probe());
    config.upstream_generation = 0;
    assert!(!tracker.update_session(2, &config));
    tracker.clear();
    assert!(!tracker.finish_probe());
    assert!(tracker.update_session(3, &config));
    assert!(!tracker.finish_probe());
    assert!(!tracker.update_session(3, &config));
    config.upstream_generation = 2;
    assert!(tracker.update_session(3, &config));
    assert!(!tracker.update_session(4, &config));
    tracker.remove_session(4);
    assert!(!tracker.finish_probe());
}

fn benchmark_generation_config() -> SessionConfig {
    SessionConfig {
        downstream: "down0".into(), reply_mark: 0, ip_forward: true,
        masquerade: crate::shared::proto::daemon::MasqueradeMode::None,
        ipv6_block: false, primary_network: Some(1),
        primary_routes: Vec::new(), fallback_network: None,
        primary_upstream_interfaces: vec!["ipsec1".into()], fallback_upstream_interfaces: Vec::new(),
        upstream_generation: 0, clients: Vec::new(), ipv6_nat: None,
    }
}
