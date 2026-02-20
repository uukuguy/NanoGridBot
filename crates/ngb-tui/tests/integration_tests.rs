//! Integration tests for ngb-tui — uses only public API + MockTransport.

use ngb_tui::{
    App, AppConfig, AppState, MockTransport, OutputChunk, ThemeName, Transport,
    MOCK_TRANSPORT,
};
use futures::StreamExt;
use std::time::Duration;

// ── AppConfig builder tests ─────────────────────────────────────────────────

#[test]
fn test_app_config_builder() {
    let config = AppConfig::new("my-workspace")
        .with_transport(MOCK_TRANSPORT)
        .with_theme(ThemeName::TokyoNight)
        .with_image("custom:latest")
        .with_data_dir("/tmp/data".into())
        .with_ws_url("ws://localhost:9090/ws")
        .with_session_id("s-1234");

    assert_eq!(config.workspace, "my-workspace");
    assert_eq!(config.transport_kind, MOCK_TRANSPORT);
    assert_eq!(config.theme_name, ThemeName::TokyoNight);
    assert_eq!(config.image, "custom:latest");
    assert_eq!(config.data_dir.to_str().unwrap(), "/tmp/data");
    assert_eq!(config.ws_url.as_deref(), Some("ws://localhost:9090/ws"));
    assert_eq!(config.session_id.as_deref(), Some("s-1234"));
}

#[test]
fn test_app_config_defaults() {
    let config = AppConfig::default();
    assert!(config.workspace.is_empty());
    assert_eq!(config.theme_name, ThemeName::CatppuccinMocha);
    assert_eq!(config.image, "claude-code:latest");
    assert!(config.ws_url.is_none());
    assert!(config.config.is_none());
    assert!(config.session_id.is_none());
}

// ── MockTransport send/receive tests ────────────────────────────────────────

#[tokio::test]
async fn test_mock_transport_creates_chunks() {
    let mut transport = MockTransport::new();

    // Send triggers the stream
    transport.send("test message").await.unwrap();

    // Collect chunks until Done
    let mut stream = transport.recv_stream();
    let mut chunks = Vec::new();

    loop {
        tokio::select! {
            chunk = stream.next() => {
                match chunk {
                    Some(OutputChunk::Done) => {
                        chunks.push(OutputChunk::Done);
                        break;
                    }
                    Some(c) => chunks.push(c),
                    None => break,
                }
            }
            _ = tokio::time::sleep(Duration::from_secs(10)) => {
                panic!("Timeout waiting for mock response");
            }
        }
    }

    // Cycle 0: ThinkingStart, ThinkingText, ThinkingEnd, Text, Done
    assert!(chunks.len() >= 4);
    assert!(matches!(&chunks[0], OutputChunk::ThinkingStart));
    assert!(matches!(&chunks.last().unwrap(), OutputChunk::Done));
}

// ── App creation tests ──────────────────────────────────────────────────────

#[test]
fn test_app_creation_with_config() {
    let config = AppConfig::new("test-ws").with_theme(ThemeName::Kanagawa);
    let app = App::with_config(config).unwrap();

    assert_eq!(app.workspace, "test-ws");
    assert!(app.messages.is_empty());
    assert!(!app.quit);
}

#[test]
fn test_app_creation_default() {
    let app = App::new().unwrap();
    assert!(app.workspace.is_empty());
    assert!(app.messages.is_empty());
}

#[test]
fn test_app_all_themes_constructable() {
    use ngb_tui::all_theme_names;
    for name in all_theme_names() {
        let config = AppConfig::default().with_theme(name);
        let _app = App::with_config(config).unwrap();
    }
}

// ── Phase 26 integration tests ──────────────────────────────────────────────

#[test]
fn test_app_state_exported() {
    // Verify AppState enum is publicly accessible with all variants
    let _idle = AppState::Idle;
    let _streaming = AppState::Streaming;
    let _thinking = AppState::Thinking;
    let _tool = AppState::ToolRunning;
    let _offline = AppState::Offline;

    // Default should be Idle
    assert_eq!(AppState::default(), AppState::Idle);
}

#[test]
fn test_app_default_state() {
    let app = App::new().unwrap();
    // New app should be empty, not quit, workspace empty
    assert!(app.messages.is_empty());
    assert!(!app.quit);
    assert!(app.workspace.is_empty());
}
