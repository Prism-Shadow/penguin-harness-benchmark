#[tokio::test]
async fn benchmark_generation_production_completion() {
    use vpnhotspotd::shared::model::SessionConfig;
    let state = Arc::new(State {
        ipsec: Mutex::new(UpstreamTracker::default()),
        nat66: nat66::ProcessResources::new(DAEMON_REPLY_MARK),
        sessions: Mutex::new(HashMap::new()),
        ipv6_nat_firewall_base: Mutex::new(false),
        neighbour_monitor: Mutex::new(None),
    });
    let (sender, _receiver) = tokio::sync::mpsc::unbounded_channel();
    let config = SessionConfig {
        downstream: "down7".into(), reply_mark: 0, ip_forward: true,
        masquerade: daemon::MasqueradeMode::None,
        ipv6_block: false, primary_network: Some(1), primary_routes: Vec::new(),
        fallback_network: None, primary_upstream_interfaces: vec!["ipsec3".into()],
        fallback_upstream_interfaces: Vec::new(), upstream_generation: 0,
        clients: Vec::new(), ipv6_nat: None,
    };
    assert!(state.ipsec.lock().await.update_session(7, &config));
    let scans = Arc::new(std::sync::atomic::AtomicUsize::new(0));
    let active = Arc::new(std::sync::atomic::AtomicUsize::new(0));
    state.run_ipsec_probes(&sender, || {
        let state = state.clone();
        let scans = scans.clone();
        let active = active.clone();
        let mut config = config.clone();
        async move {
            assert_eq!(active.fetch_add(1, Ordering::SeqCst), 0);
            let attempt = scans.fetch_add(1, Ordering::SeqCst);
            assert!(attempt < 3, "unchanged state must not cause a probe loop");
            if attempt < 2 {
                config.upstream_generation = 1 + attempt as u64;
                assert!(!state.ipsec.lock().await.update_session(7, &config));
                assert!(!state.ipsec.lock().await.update_session(7, &config));
            }
            tokio::task::yield_now().await;
            assert_eq!(active.fetch_sub(1, Ordering::SeqCst), 1);
            if attempt == 0 { Err(io::Error::from_raw_os_error(libc::EIO)) }
            else { Ok(Vec::new()) }
        }
    }).await;
    assert_eq!(scans.load(Ordering::SeqCst), 3);
    assert_eq!(active.load(Ordering::SeqCst), 0);
    assert!(!state.ipsec.lock().await.finish_probe());
}
