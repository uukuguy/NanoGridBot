use std::sync::Arc;

use anyhow::{bail, Context};
use clap::{Parser, Subcommand};
use ngb_channels::TelegramChannel;
use ngb_config::Config;
use ngb_core::ipc_handler::ChannelSender;
use ngb_core::Orchestrator;
use ngb_db::{BindingRepository, Database, TokenRepository, WorkspaceRepository};
use ngb_tui::{AppConfig, ThemeName, PIPE_TRANSPORT, IPC_TRANSPORT, WS_TRANSPORT};
use ngb_types::Workspace;
use tracing::{error, info};
use uuid::Uuid;

#[derive(Parser)]
#[command(name = "ngb", about = "NanoGridBot - Agent Runtime", version)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand)]
enum Commands {
    /// Start the orchestrator and channel listeners
    Serve,
    /// Manage workspaces
    Workspace {
        #[command(subcommand)]
        action: WorkspaceAction,
    },
    /// Start the TUI shell
    Shell {
        /// Workspace name to connect to
        workspace: String,
        /// Transport mode: pipe, ipc, or ws
        #[arg(long, default_value = "pipe")]
        transport: String,
        /// Theme name: catppuccin-mocha, catppuccin-latte, kanagawa, rose-pine, rose-pine-dawn, tokyo-night, midnight, terminal
        #[arg(long)]
        theme: Option<String>,
    },
}

#[derive(Subcommand)]
enum WorkspaceAction {
    /// Create a new workspace and generate an access token
    Create {
        /// Name for the workspace
        name: String,
    },
    /// List all workspaces and their bindings
    List,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Serve => serve().await?,
        Commands::Workspace { action } => workspace(action).await?,
        Commands::Shell {
            workspace,
            transport,
            theme,
        } => shell(workspace, transport, theme)?,
    }
    Ok(())
}

fn shell(workspace: String, transport: String, theme: Option<String>) -> anyhow::Result<()> {
    // Parse transport kind
    let transport_kind = match transport.as_str() {
        "pipe" => PIPE_TRANSPORT,
        "ipc" => IPC_TRANSPORT,
        "ws" => WS_TRANSPORT,
        _ => bail!("Invalid transport: {}. Use pipe, ipc, or ws", transport),
    };

    // Parse theme
    let theme_name = if let Some(t) = theme {
        match t.as_str() {
            "catppuccin-mocha" => ThemeName::CatppuccinMocha,
            "catppuccin-latte" => ThemeName::CatppuccinLatte,
            "kanagawa" => ThemeName::Kanagawa,
            "rose-pine" => ThemeName::RosePine,
            "rose-pine-dawn" => ThemeName::RosePineDawn,
            "tokyo-night" => ThemeName::TokyoNight,
            "midnight" => ThemeName::Midnight,
            "terminal" => ThemeName::Terminal,
            _ => bail!(
                "Invalid theme: {}. Use catppuccin-mocha, catppuccin-latte, kanagawa, rose-pine, rose-pine-dawn, tokyo-night, midnight, or terminal",
                t
            ),
        }
    } else {
        ThemeName::CatppuccinMocha
    };

    // Load config for data directory
    let config = Config::load().context("Failed to load configuration")?;
    let data_dir = config.store_dir.join("workspaces").join(&workspace);

    // Create app config and run
    let app_config = AppConfig::new(workspace)
        .with_transport(transport_kind)
        .with_theme(theme_name)
        .with_data_dir(data_dir)
        .with_image(&config.container_image);

    let mut app = ngb_tui::App::with_config(app_config)?;
    app.run()?;

    Ok(())
}

async fn workspace(action: WorkspaceAction) -> anyhow::Result<()> {
    let config = Config::load().context("Failed to load configuration")?;
    config
        .create_directories()
        .context("Failed to create directories")?;

    std::fs::create_dir_all(config.db_path.parent().unwrap_or(&config.store_dir))
        .context("Failed to create database directory")?;
    let db = Database::new(&config.db_path)
        .await
        .context("Failed to connect to database")?;
    db.initialize()
        .await
        .context("Failed to initialize database schema")?;

    match action {
        WorkspaceAction::Create { name } => workspace_create(&db, &name).await?,
        WorkspaceAction::List => workspace_list(&db).await?,
    }

    db.close().await;
    Ok(())
}

async fn workspace_create(db: &Database, name: &str) -> anyhow::Result<()> {
    let ws_id = format!("ws-{}", &Uuid::new_v4().simple().to_string()[..8]);
    let folder = name.to_string();

    let ws = Workspace {
        id: ws_id.clone(),
        name: name.to_string(),
        owner: "cli".to_string(),
        folder,
        shared: false,
        container_config: None,
    };

    let ws_repo = WorkspaceRepository::new(db);
    ws_repo
        .save(&ws)
        .await
        .map_err(|e| anyhow::anyhow!("{e}"))?;

    let token_repo = TokenRepository::new(db);
    let token = token_repo
        .create_token(&ws_id)
        .await
        .map_err(|e| anyhow::anyhow!("{e}"))?;

    println!("Workspace created:");
    println!("  ID:     {ws_id}");
    println!("  Name:   {name}");
    println!("  Folder: {}", ws.folder);
    println!("  Token:  {token}");
    println!();
    println!("Send this token in a chat to bind it to this workspace.");

    Ok(())
}

async fn workspace_list(db: &Database) -> anyhow::Result<()> {
    let ws_repo = WorkspaceRepository::new(db);
    let workspaces = ws_repo
        .get_all()
        .await
        .map_err(|e| anyhow::anyhow!("{e}"))?;

    if workspaces.is_empty() {
        println!("No workspaces found. Create one with: ngb workspace create <name>");
        return Ok(());
    }

    let binding_repo = BindingRepository::new(db);

    println!(
        "{:<12} {:<20} {:<20} BINDINGS",
        "ID", "NAME", "FOLDER"
    );
    println!("{}", "-".repeat(72));

    for ws in &workspaces {
        let bindings = binding_repo
            .get_by_workspace(&ws.id)
            .await
            .map_err(|e| anyhow::anyhow!("{e}"))?;

        let binding_str = if bindings.is_empty() {
            "(none)".to_string()
        } else {
            bindings
                .iter()
                .map(|b| b.channel_jid.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        };

        println!(
            "{:<12} {:<20} {:<20} {}",
            ws.id, ws.name, ws.folder, binding_str
        );
    }

    println!();
    println!("{} workspace(s) total", workspaces.len());

    Ok(())
}

async fn serve() -> anyhow::Result<()> {
    // 1. Init logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new("info")),
        )
        .init();

    info!("NanoGridBot starting...");

    // 2. Load config
    let config = Config::load().context("Failed to load configuration")?;
    config
        .create_directories()
        .context("Failed to create directories")?;
    info!(
        project = %config.project_name,
        image = %config.container_image,
        "Configuration loaded"
    );

    // 3. Init database
    std::fs::create_dir_all(config.db_path.parent().unwrap_or(&config.store_dir))
        .context("Failed to create database directory")?;
    let db = Arc::new(
        Database::new(&config.db_path)
            .await
            .context("Failed to connect to database")?,
    );
    db.initialize()
        .await
        .context("Failed to initialize database schema")?;
    info!("Database initialized");

    // 4. Create channels
    let mut channels: Vec<Box<dyn ChannelSender>> = Vec::new();
    let mut listener_handles = Vec::new();

    if let Some(ref token) = config.telegram_bot_token {
        let tg = TelegramChannel::new(token, db.clone());
        let handle = tg.start();
        listener_handles.push(handle);
        channels.push(Box::new(tg));
        info!("Telegram channel enabled");
    } else {
        bail!("TELEGRAM_BOT_TOKEN is required for serve mode. Set it in .env or environment.");
    }

    // 5. Pre-flight checks
    let image = &config.container_image;
    let docker_ok = std::process::Command::new("docker")
        .args(["image", "inspect", image])
        .stdout(std::process::Stdio::null())
        .stderr(std::process::Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false);
    if !docker_ok {
        error!(
            image = %image,
            "Docker image not found. Run: make docker-build"
        );
        bail!("Docker image '{image}' not found. Build it first with: make docker-build");
    }
    info!(image = %image, "Docker image verified");

    // 6. Create and start orchestrator
    let orchestrator = Arc::new(Orchestrator::new(config, db.clone(), channels));
    orchestrator
        .start()
        .await
        .context("Failed to start orchestrator")?;
    info!("Orchestrator started");

    // 7. Run message loop + wait for shutdown
    let orch = orchestrator.clone();
    let message_loop = tokio::spawn(async move {
        if let Err(e) = orch.run_message_loop().await {
            error!(error = %e, "Message loop error");
        }
    });

    // Wait for Ctrl+C
    info!("NanoGridBot is running. Press Ctrl+C to stop.");
    tokio::signal::ctrl_c()
        .await
        .context("Failed to listen for Ctrl+C")?;

    info!("Shutting down...");
    let _ = orchestrator.stop().await;

    // Abort listener tasks
    for handle in listener_handles {
        handle.abort();
    }
    message_loop.abort();

    db.close().await;
    info!("NanoGridBot stopped.");
    Ok(())
}
