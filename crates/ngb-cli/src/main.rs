use std::sync::Arc;

use anyhow::{bail, Context};
use clap::{Parser, Subcommand};
use ngb_channels::TelegramChannel;
use ngb_config::Config;
use ngb_core::ipc_handler::ChannelSender;
use ngb_core::Orchestrator;
use ngb_db::Database;
use tracing::{error, info};

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
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();
    match cli.command {
        Commands::Serve => serve().await?,
    }
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

    // 5. Create and start orchestrator
    let orchestrator = Arc::new(Orchestrator::new(config, db.clone(), channels));
    orchestrator
        .start()
        .await
        .context("Failed to start orchestrator")?;
    info!("Orchestrator started");

    // 6. Run message loop + wait for shutdown
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
