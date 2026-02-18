//! Tree view module for displaying message threads
//!
//! Provides tree structure for displaying conversation threads/replies.

/// Tree part for visual representation
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum TreePart {
    /// ├──
    Edge,
    /// │
    Line,
    /// └──
    Corner,
    /// (space)
    Blank,
}

impl TreePart {
    /// Get ASCII/Unicode art representation
    pub fn ascii_art(self) -> &'static str {
        match self {
            Self::Edge => "├── ",
            Self::Line => "│   ",
            Self::Corner => "└── ",
            Self::Blank => "    ",
        }
    }
}

/// Tree node for message threads
#[derive(Debug, Clone)]
pub struct TreeNode {
    /// Unique identifier for this node
    pub id: String,
    /// Parent node id (None for root)
    pub parent_id: Option<String>,
    /// Child node ids
    pub children: Vec<String>,
    /// Depth level (0 = root)
    pub depth: usize,
    /// Whether this is the last child in its parent
    pub is_last: bool,
}

impl TreeNode {
    /// Create a new tree node
    pub fn new(id: String, parent_id: Option<String>, depth: usize, is_last: bool) -> Self {
        Self {
            id,
            parent_id,
            children: Vec::new(),
            depth,
            is_last,
        }
    }

    /// Get the visual prefix for rendering this node
    pub fn prefix(&self, all_nodes: &Tree) -> String {
        if self.depth == 0 {
            return String::new();
        }

        let mut prefix = String::new();

        // Build prefix based on ancestors
        let mut current_id = self.parent_id.clone();

        while let Some(parent_id) = current_id {
            if let Some(parent) = all_nodes.get(&parent_id) {
                let part = if parent.is_last {
                    TreePart::Blank
                } else {
                    TreePart::Line
                };
                prefix.insert_str(0, part.ascii_art());
                current_id = parent.parent_id.clone();
            } else {
                break;
            }
        }

        // Add current node's prefix
        let current_part = if self.is_last {
            TreePart::Corner
        } else {
            TreePart::Edge
        };
        prefix.push_str(current_part.ascii_art());

        prefix
    }
}

/// Collection of tree nodes (tree structure)
#[derive(Debug, Clone, Default)]
pub struct Tree {
    nodes: std::collections::HashMap<String, TreeNode>,
}

impl Tree {
    /// Create a new empty tree
    pub fn new() -> Self {
        Self {
            nodes: std::collections::HashMap::new(),
        }
    }

    /// Add a node to the tree
    pub fn add_node(&mut self, node: TreeNode) {
        // Update parent's children list
        if let Some(parent_id) = &node.parent_id {
            if let Some(parent) = self.nodes.get_mut(parent_id) {
                parent.children.push(node.id.clone());
            }
        }
        self.nodes.insert(node.id.clone(), node);
    }

    /// Get a node by id
    pub fn get(&self, id: &str) -> Option<&TreeNode> {
        self.nodes.get(id)
    }

    /// Get all root nodes (nodes without parent)
    pub fn roots(&self) -> Vec<&TreeNode> {
        self.nodes
            .values()
            .filter(|n| n.parent_id.is_none())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_tree_parts() {
        assert_eq!(TreePart::Edge.ascii_art(), "├── ");
        assert_eq!(TreePart::Line.ascii_art(), "│   ");
        assert_eq!(TreePart::Corner.ascii_art(), "└── ");
        assert_eq!(TreePart::Blank.ascii_art(), "    ");
    }

    #[test]
    fn test_tree_node() {
        let node = TreeNode::new(
            "child1".to_string(),
            Some("parent".to_string()),
            1,
            true,
        );
        assert_eq!(node.depth, 1);
        assert!(node.is_last);
        assert_eq!(node.parent_id, Some("parent".to_string()));
    }
}
