//! Search Engine abstraction layer for NanoGridBot TUI
//!
//! Provides a trait for implementing different search backends
//! for command history, inspired byatuin's search engine design.

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

/// Search result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub id: String,
    pub content: String,
    pub timestamp: i64,
    pub score: f64,
    pub metadata: Option<SearchMetadata>,
}

/// Search metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchMetadata {
    pub command: Option<String>,
    pub exit_code: Option<i32>,
    pub duration_ms: Option<u64>,
}

/// Search filter
#[derive(Debug, Clone, Default)]
pub struct SearchFilter {
    pub query: Option<String>,
    pub date_from: Option<i64>,
    pub date_to: Option<i64>,
    pub exit_code: Option<i32>,
    pub limit: Option<usize>,
}

/// Search engine trait - supports command history search
#[async_trait]
pub trait SearchEngine: Send + Sync {
    /// Execute search
    async fn search(&self, query: &str) -> Vec<SearchResult>;

    /// Filter results
    async fn filter(&mut self, filter: SearchFilter);

    /// Get total count
    fn count(&self) -> usize;
}

/// History engine - loads command history from local storage
pub struct HistoryEngine {
    results: Vec<SearchResult>,
}

impl HistoryEngine {
    pub fn new() -> Self {
        Self { results: Vec::new() }
    }

    /// Load history from file
    pub async fn load_history(&mut self, path: &std::path::Path) -> Result<(), Box<dyn std::error::Error>> {
        // Simple implementation: just ensure directory exists
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent)?;
        }
        Ok(())
    }

    /// Add a result to the engine
    pub fn add_result(&mut self, result: SearchResult) {
        self.results.push(result);
    }

    /// Get all results
    pub fn results(&self) -> &[SearchResult] {
        &self.results
    }

    /// Clear all results
    pub fn clear(&mut self) {
        self.results.clear();
    }
}

impl Default for HistoryEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl SearchEngine for HistoryEngine {
    async fn search(&self, query: &str) -> Vec<SearchResult> {
        if query.is_empty() {
            return self.results.clone();
        }

        // Simple contains match
        self.results
            .iter()
            .filter(|r| r.content.to_lowercase().contains(&query.to_lowercase()))
            .cloned()
            .collect()
    }

    async fn filter(&mut self, filter: SearchFilter) {
        if let Some(query) = filter.query {
            let results: Vec<SearchResult> = self
                .results
                .iter()
                .filter(|r| r.content.to_lowercase().contains(&query.to_lowercase()))
                .cloned()
                .collect();
            self.results = results;
        }

        if let Some(date_from) = filter.date_from {
            self.results.retain(|r| r.timestamp >= date_from);
        }

        if let Some(date_to) = filter.date_to {
            self.results.retain(|r| r.timestamp <= date_to);
        }

        if let Some(exit_code) = filter.exit_code {
            self.results.retain(|r| {
                r.metadata
                    .as_ref()
                    .map(|m| m.exit_code == Some(exit_code))
                    .unwrap_or(false)
            });
        }

        if let Some(limit) = filter.limit {
            self.results.truncate(limit);
        }
    }

    fn count(&self) -> usize {
        self.results.len()
    }
}

/// Create a new history engine
pub fn create_history_engine() -> HistoryEngine {
    HistoryEngine::new()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_history_engine_search() {
        let mut engine = HistoryEngine::new();
        engine.add_result(SearchResult {
            id: "1".to_string(),
            content: "ls -la".to_string(),
            timestamp: 1000,
            score: 1.0,
            metadata: None,
        });
        engine.add_result(SearchResult {
            id: "2".to_string(),
            content: "git status".to_string(),
            timestamp: 2000,
            score: 1.0,
            metadata: None,
        });

        let results = engine.search("ls").await;
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].content, "ls -la");
    }

    #[test]
    fn test_history_engine_count() {
        let mut engine = HistoryEngine::new();
        engine.add_result(SearchResult {
            id: "1".to_string(),
            content: "test".to_string(),
            timestamp: 1000,
            score: 1.0,
            metadata: None,
        });

        assert_eq!(engine.count(), 1);
    }
}
