use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::{OnceLock, RwLock};

use ngb_types::{ChannelType, NanoGridBotError, Result};

/// Application configuration.
#[derive(Debug, Clone)]
pub struct Config {
    // Project settings
    pub project_name: String,
    pub version: String,
    pub debug: bool,

    // Paths
    pub base_dir: PathBuf,
    pub data_dir: PathBuf,
    pub store_dir: PathBuf,
    pub groups_dir: PathBuf,
    pub workspaces_dir: PathBuf,
    pub db_path: PathBuf,
    pub whatsapp_session_path: PathBuf,

    // API keys
    pub openai_api_key: Option<String>,
    pub anthropic_api_key: Option<String>,

    // Channel configurations
    pub telegram_bot_token: Option<String>,
    pub slack_bot_token: Option<String>,
    pub slack_signing_secret: Option<String>,
    pub discord_bot_token: Option<String>,

    // QQ
    pub qq_host: String,
    pub qq_port: u16,

    // Feishu
    pub feishu_app_id: Option<String>,
    pub feishu_app_secret: Option<String>,

    // WeCom
    pub wecom_corp_id: Option<String>,
    pub wecom_agent_id: Option<String>,
    pub wecom_secret: Option<String>,

    // DingTalk
    pub dingtalk_app_key: Option<String>,
    pub dingtalk_app_secret: Option<String>,

    // Claude settings
    pub claude_api_url: String,
    pub claude_api_version: String,
    pub claude_model: String,
    pub claude_max_tokens: u32,

    // CLI settings
    pub cli_default_group: String,

    // Container settings
    pub container_timeout: u64,
    pub container_max_output_size: usize,
    pub container_max_concurrent: usize,
    pub container_image: String,

    // Assistant settings
    pub assistant_name: String,
    pub trigger_pattern: Option<String>,

    // Performance
    pub poll_interval: u64,
    pub max_messages_per_minute: u32,
    pub message_cache_size: usize,
    pub batch_size: usize,
    pub db_connection_pool_size: u32,
    pub ipc_file_buffer_size: usize,

    // Logging
    pub log_level: String,
    pub log_format: String,
    pub log_rotation: String,
    pub log_retention: String,

    // Web
    pub web_host: String,
    pub web_port: u16,
}

impl Config {
    /// Load configuration from environment variables (with dotenvy).
    pub fn load() -> Result<Self> {
        // Load .env file if it exists (ignore errors — file may not exist)
        let _ = dotenvy::dotenv();

        let base_dir = env_or("BASE_DIR", || {
            std::env::current_dir()
                .unwrap_or_default()
                .to_string_lossy()
                .to_string()
        });
        let base = PathBuf::from(&base_dir);

        let data_dir = env_path_or("DATA_DIR", || base.join("data"));
        let store_dir = env_path_or("STORE_DIR", || base.join("store"));
        let groups_dir = env_path_or("GROUPS_DIR", || base.join("groups"));
        let workspaces_dir = env_path_or("WORKSPACES_DIR", || base.join("workspaces"));

        let config = Config {
            project_name: env_or("PROJECT_NAME", || "NanoGridBot".to_string()),
            version: env_or("VERSION", || "0.1.0-alpha".to_string()),
            debug: env_bool("DEBUG", false),

            base_dir: base.clone(),
            data_dir: data_dir.clone(),
            store_dir: store_dir.clone(),
            groups_dir: groups_dir.clone(),
            workspaces_dir: workspaces_dir.clone(),
            db_path: env_path_or("DB_PATH", || store_dir.join("messages.db")),
            whatsapp_session_path: env_path_or("WHATSAPP_SESSION_PATH", || {
                store_dir.join("whatsapp_session")
            }),

            openai_api_key: env_opt("OPENAI_API_KEY"),
            anthropic_api_key: env_opt("ANTHROPIC_API_KEY"),

            telegram_bot_token: env_opt("TELEGRAM_BOT_TOKEN"),
            slack_bot_token: env_opt("SLACK_BOT_TOKEN"),
            slack_signing_secret: env_opt("SLACK_SIGNING_SECRET"),
            discord_bot_token: env_opt("DISCORD_BOT_TOKEN"),

            qq_host: env_or("QQ_HOST", || "127.0.0.1".to_string()),
            qq_port: env_u16("QQ_PORT", 20000),

            feishu_app_id: env_opt("FEISHU_APP_ID"),
            feishu_app_secret: env_opt("FEISHU_APP_SECRET"),

            wecom_corp_id: env_opt("WECOM_CORP_ID"),
            wecom_agent_id: env_opt("WECOM_AGENT_ID"),
            wecom_secret: env_opt("WECOM_SECRET"),

            dingtalk_app_key: env_opt("DINGTALK_APP_KEY"),
            dingtalk_app_secret: env_opt("DINGTALK_APP_SECRET"),

            claude_api_url: env_or("CLAUDE_API_URL", || "https://api.anthropic.com".to_string()),
            claude_api_version: env_or("CLAUDE_API_VERSION", || "2023-06-01".to_string()),
            claude_model: env_or("CLAUDE_MODEL", || "claude-sonnet-4-20250514".to_string()),
            claude_max_tokens: env_u32("CLAUDE_MAX_TOKENS", 4096),

            cli_default_group: env_or("CLI_DEFAULT_GROUP", || "cli".to_string()),

            container_timeout: env_u64("CONTAINER_TIMEOUT", 300),
            container_max_output_size: env_usize("CONTAINER_MAX_OUTPUT_SIZE", 100_000),
            container_max_concurrent: env_usize("CONTAINER_MAX_CONCURRENT_CONTAINERS", 5),
            container_image: env_or("CONTAINER_IMAGE", || "nanogridbot-agent:latest".to_string()),

            assistant_name: env_or("ASSISTANT_NAME", || "Andy".to_string()),
            trigger_pattern: env_opt("TRIGGER_PATTERN"),

            poll_interval: env_u64("POLL_INTERVAL", 2000),
            max_messages_per_minute: env_u32("MAX_MESSAGES_PER_MINUTE", 10),
            message_cache_size: env_usize("MESSAGE_CACHE_SIZE", 1000),
            batch_size: env_usize("BATCH_SIZE", 100),
            db_connection_pool_size: env_u32("DB_CONNECTION_POOL_SIZE", 5),
            ipc_file_buffer_size: env_usize("IPC_FILE_BUFFER_SIZE", 8192),

            log_level: env_or("LOG_LEVEL", || "INFO".to_string()),
            log_format: env_or("LOG_FORMAT", || {
                "{time} | {level} | {target}:{line} - {message}".to_string()
            }),
            log_rotation: env_or("LOG_ROTATION", || "10 MB".to_string()),
            log_retention: env_or("LOG_RETENTION", || "7 days".to_string()),

            web_host: env_or("WEB_HOST", || "0.0.0.0".to_string()),
            web_port: env_u16("WEB_PORT", 8080),
        };

        Ok(config)
    }

    /// Create required directories.
    pub fn create_directories(&self) -> Result<()> {
        let dirs = [
            self.data_dir.clone(),
            self.store_dir.clone(),
            self.groups_dir.clone(),
            self.workspaces_dir.clone(),
            self.data_dir.join("ipc"),
            self.data_dir.join("sessions"),
            self.data_dir.join("env"),
            self.store_dir.join("auth"),
            self.whatsapp_session_path.clone(),
        ];

        for dir in &dirs {
            std::fs::create_dir_all(dir).map_err(|e| {
                NanoGridBotError::Config(format!(
                    "Failed to create directory {}: {e}",
                    dir.display()
                ))
            })?;
        }

        Ok(())
    }

    /// Get configuration for a specific channel.
    pub fn get_channel_config(&self, channel: ChannelType) -> HashMap<String, String> {
        let mut map = HashMap::new();
        match channel {
            ChannelType::Telegram => {
                if let Some(ref token) = self.telegram_bot_token {
                    map.insert("bot_token".to_string(), token.clone());
                }
            }
            ChannelType::Slack => {
                if let Some(ref token) = self.slack_bot_token {
                    map.insert("bot_token".to_string(), token.clone());
                }
                if let Some(ref secret) = self.slack_signing_secret {
                    map.insert("signing_secret".to_string(), secret.clone());
                }
            }
            ChannelType::Discord => {
                if let Some(ref token) = self.discord_bot_token {
                    map.insert("bot_token".to_string(), token.clone());
                }
            }
            ChannelType::Whatsapp => {
                map.insert(
                    "session_path".to_string(),
                    self.whatsapp_session_path.to_string_lossy().to_string(),
                );
            }
            ChannelType::Qq => {
                map.insert("host".to_string(), self.qq_host.clone());
                map.insert("port".to_string(), self.qq_port.to_string());
            }
            ChannelType::Feishu => {
                if let Some(ref id) = self.feishu_app_id {
                    map.insert("app_id".to_string(), id.clone());
                }
                if let Some(ref secret) = self.feishu_app_secret {
                    map.insert("app_secret".to_string(), secret.clone());
                }
            }
            ChannelType::Wecom => {
                if let Some(ref id) = self.wecom_corp_id {
                    map.insert("corp_id".to_string(), id.clone());
                }
                if let Some(ref id) = self.wecom_agent_id {
                    map.insert("agent_id".to_string(), id.clone());
                }
                if let Some(ref secret) = self.wecom_secret {
                    map.insert("secret".to_string(), secret.clone());
                }
            }
            ChannelType::Dingtalk => {
                if let Some(ref key) = self.dingtalk_app_key {
                    map.insert("app_key".to_string(), key.clone());
                }
                if let Some(ref secret) = self.dingtalk_app_secret {
                    map.insert("app_secret".to_string(), secret.clone());
                }
            }
        }
        map
    }
}

// ---------------------------------------------------------------------------
// Global singleton
// ---------------------------------------------------------------------------

static CONFIG: OnceLock<RwLock<Config>> = OnceLock::new();

/// Get (or lazily initialise) the global configuration.
pub fn get_config() -> Result<Config> {
    let lock = CONFIG.get_or_init(|| {
        let cfg = Config::load().expect("Failed to load initial config");
        RwLock::new(cfg)
    });
    let guard = lock
        .read()
        .map_err(|e| NanoGridBotError::Config(format!("Config lock poisoned: {e}")))?;
    Ok(guard.clone())
}

/// Reload configuration from environment.
pub fn reload_config() -> Result<Config> {
    let new_cfg = Config::load()?;
    let lock = CONFIG.get_or_init(|| RwLock::new(new_cfg.clone()));
    let mut guard = lock
        .write()
        .map_err(|e| NanoGridBotError::Config(format!("Config lock poisoned: {e}")))?;
    *guard = new_cfg.clone();
    Ok(new_cfg)
}

// ---------------------------------------------------------------------------
// Env helpers
// ---------------------------------------------------------------------------

fn env_or(key: &str, default: impl FnOnce() -> String) -> String {
    std::env::var(key).unwrap_or_else(|_| default())
}

fn env_opt(key: &str) -> Option<String> {
    std::env::var(key).ok().filter(|s| !s.is_empty())
}

fn env_bool(key: &str, default: bool) -> bool {
    std::env::var(key)
        .ok()
        .map(|v| matches!(v.to_lowercase().as_str(), "true" | "1" | "yes"))
        .unwrap_or(default)
}

fn env_u16(key: &str, default: u16) -> u16 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u32(key: &str, default: u32) -> u32 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_u64(key: &str, default: u64) -> u64 {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_usize(key: &str, default: usize) -> usize {
    std::env::var(key)
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(default)
}

fn env_path_or(key: &str, default: impl FnOnce() -> PathBuf) -> PathBuf {
    std::env::var(key)
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(default)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn config_load_defaults() {
        let cfg = Config::load().unwrap();
        assert_eq!(cfg.project_name, "NanoGridBot");
        assert_eq!(cfg.version, "0.1.0-alpha");
        assert_eq!(cfg.claude_max_tokens, 4096);
        assert_eq!(cfg.container_timeout, 300);
        assert_eq!(cfg.qq_host, "127.0.0.1");
        assert_eq!(cfg.qq_port, 20000);
        assert_eq!(cfg.message_cache_size, 1000);
    }

    #[test]
    fn config_env_override() {
        // Use a unique env var unlikely to collide
        std::env::set_var("BATCH_SIZE", "999");
        let cfg = Config::load().unwrap();
        assert_eq!(cfg.batch_size, 999);
        std::env::remove_var("BATCH_SIZE");
    }

    #[test]
    fn config_channel_config_telegram() {
        std::env::set_var("TELEGRAM_BOT_TOKEN", "test-token-123");
        let cfg = Config::load().unwrap();
        let channel_cfg = cfg.get_channel_config(ChannelType::Telegram);
        assert_eq!(channel_cfg.get("bot_token").unwrap(), "test-token-123");
        std::env::remove_var("TELEGRAM_BOT_TOKEN");
    }

    #[test]
    fn config_channel_config_whatsapp() {
        let cfg = Config::load().unwrap();
        let channel_cfg = cfg.get_channel_config(ChannelType::Whatsapp);
        assert!(channel_cfg.contains_key("session_path"));
    }

    #[test]
    fn config_channel_config_qq() {
        let cfg = Config::load().unwrap();
        let channel_cfg = cfg.get_channel_config(ChannelType::Qq);
        assert_eq!(channel_cfg.get("host").unwrap(), "127.0.0.1");
        assert_eq!(channel_cfg.get("port").unwrap(), "20000");
    }

    #[test]
    fn config_create_directories() {
        let tmp = tempfile::tempdir().unwrap();
        let base = tmp.path().to_path_buf();

        let cfg = Config {
            project_name: "test".to_string(),
            version: "0.0.1".to_string(),
            debug: false,
            base_dir: base.clone(),
            data_dir: base.join("data"),
            store_dir: base.join("store"),
            groups_dir: base.join("groups"),
            workspaces_dir: base.join("workspaces"),
            db_path: base.join("store/messages.db"),
            whatsapp_session_path: base.join("store/whatsapp_session"),
            openai_api_key: None,
            anthropic_api_key: None,
            telegram_bot_token: None,
            slack_bot_token: None,
            slack_signing_secret: None,
            discord_bot_token: None,
            qq_host: "127.0.0.1".to_string(),
            qq_port: 20000,
            feishu_app_id: None,
            feishu_app_secret: None,
            wecom_corp_id: None,
            wecom_agent_id: None,
            wecom_secret: None,
            dingtalk_app_key: None,
            dingtalk_app_secret: None,
            claude_api_url: "https://api.anthropic.com".to_string(),
            claude_api_version: "2023-06-01".to_string(),
            claude_model: "claude-sonnet-4-20250514".to_string(),
            claude_max_tokens: 4096,
            cli_default_group: "cli".to_string(),
            container_timeout: 300,
            container_max_output_size: 100_000,
            container_max_concurrent: 5,
            container_image: "nanogridbot-agent:latest".to_string(),
            assistant_name: "Andy".to_string(),
            trigger_pattern: None,
            poll_interval: 2000,
            max_messages_per_minute: 10,
            message_cache_size: 1000,
            batch_size: 100,
            db_connection_pool_size: 5,
            ipc_file_buffer_size: 8192,
            log_level: "INFO".to_string(),
            log_format: "default".to_string(),
            log_rotation: "10 MB".to_string(),
            log_retention: "7 days".to_string(),
            web_host: "0.0.0.0".to_string(),
            web_port: 8080,
        };

        cfg.create_directories().unwrap();

        assert!(base.join("data").exists());
        assert!(base.join("store").exists());
        assert!(base.join("groups").exists());
        assert!(base.join("data/ipc").exists());
        assert!(base.join("data/sessions").exists());
        assert!(base.join("data/env").exists());
        assert!(base.join("store/auth").exists());
        assert!(base.join("store/whatsapp_session").exists());
    }
}
