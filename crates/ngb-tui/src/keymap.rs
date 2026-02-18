//! Conditional keybinding system for NanoGridBot TUI
//!
//! Provides a declarative way to define keybindings with conditions,
//! inspired by atuin's approach to terminal keybindings.

use crossterm::event::{KeyCode, KeyModifiers};

/// Key binding action
#[derive(Debug, Clone, PartialEq)]
pub enum Action {
    // Cursor movement
    CursorLeft,
    CursorRight,
    CursorWordLeft,
    CursorWordRight,
    CursorHome,
    CursorEnd,

    // Editing
    InsertChar(char),
    Delete,
    DeleteWord,
    Backspace,
    Clear,

    // Submission
    Submit,

    // Scrolling
    ScrollUp,
    ScrollDown,
    PageUp,
    PageDown,

    // Mode switching
    EnterNormalMode,
    EnterInsertMode,

    // Application-level
    Quit,
    Interrupt,
    ClearScreen,
}

/// Conditional atom - for conditional keybindings
#[derive(Debug, Clone, PartialEq)]
pub enum ConditionAtom {
    CursorAtStart,
    CursorAtEnd,
    InputEmpty,
    InputNotEmpty,
    ListAtEnd,
    ListAtStart,
    HasResults,
    NoResults,
}

/// Evaluation context for condition evaluation
#[derive(Debug, Clone)]
pub struct EvalContext {
    pub cursor_position: usize,
    pub input_width: usize,
    pub input_byte_len: usize,
    pub selected_index: usize,
    pub results_len: usize,
    pub original_input_empty: bool,
}

impl EvalContext {
    /// Evaluate a condition atom
    pub fn evaluate(&self, cond: &ConditionAtom) -> bool {
        match cond {
            ConditionAtom::CursorAtStart => self.cursor_position == 0,
            ConditionAtom::CursorAtEnd => self.cursor_position >= self.input_byte_len,
            ConditionAtom::InputEmpty => self.input_byte_len == 0,
            ConditionAtom::InputNotEmpty => self.input_byte_len > 0,
            ConditionAtom::ListAtEnd => {
                self.results_len > 0 && self.selected_index >= self.results_len.saturating_sub(1)
            }
            ConditionAtom::ListAtStart => self.selected_index == 0,
            ConditionAtom::HasResults => self.results_len > 0,
            ConditionAtom::NoResults => self.results_len == 0,
        }
    }
}

/// Key binding definition
#[derive(Debug, Clone)]
pub struct KeyBinding {
    pub key: (KeyCode, KeyModifiers),
    pub action: Action,
    pub condition: Option<ConditionAtom>,
}

impl KeyBinding {
    /// Check if this binding matches the given key event
    pub fn matches(&self, code: KeyCode, modifiers: KeyModifiers) -> bool {
        self.key == (code, modifiers)
    }

    /// Check if the condition is satisfied (if any)
    pub fn is_condition_satisfied(&self, ctx: &EvalContext) -> bool {
        self.condition
            .as_ref()
            .map(|c| ctx.evaluate(c))
            .unwrap_or(true)
    }
}

/// Default keybindings for NanoGridBot TUI
pub fn default_keybindings() -> Vec<KeyBinding> {
    vec![
        // Ctrl+C: Clear when input is empty, interrupt when has content
        KeyBinding {
            key: (KeyCode::Char('c'), KeyModifiers::CONTROL),
            action: Action::Interrupt,
            condition: Some(ConditionAtom::InputNotEmpty),
        },
        KeyBinding {
            key: (KeyCode::Char('c'), KeyModifiers::CONTROL),
            action: Action::Clear,
            condition: Some(ConditionAtom::InputEmpty),
        },
        // Enter: Submit when input is not empty
        KeyBinding {
            key: (KeyCode::Enter, KeyModifiers::NONE),
            action: Action::Submit,
            condition: Some(ConditionAtom::InputNotEmpty),
        },
        // Ctrl+Left/Right: Word movement
        KeyBinding {
            key: (KeyCode::Left, KeyModifiers::CONTROL),
            action: Action::CursorWordLeft,
            condition: None,
        },
        KeyBinding {
            key: (KeyCode::Right, KeyModifiers::CONTROL),
            action: Action::CursorWordRight,
            condition: None,
        },
        // Home/End: Line start/end
        KeyBinding {
            key: (KeyCode::Home, KeyModifiers::NONE),
            action: Action::CursorHome,
            condition: None,
        },
        KeyBinding {
            key: (KeyCode::End, KeyModifiers::NONE),
            action: Action::CursorEnd,
            condition: None,
        },
        // Arrow keys: Basic movement
        KeyBinding {
            key: (KeyCode::Left, KeyModifiers::NONE),
            action: Action::CursorLeft,
            condition: None,
        },
        KeyBinding {
            key: (KeyCode::Right, KeyModifiers::NONE),
            action: Action::CursorRight,
            condition: None,
        },
        // Backspace and Delete
        KeyBinding {
            key: (KeyCode::Backspace, KeyModifiers::NONE),
            action: Action::Backspace,
            condition: Some(ConditionAtom::CursorAtStart),
        },
        KeyBinding {
            key: (KeyCode::Delete, KeyModifiers::NONE),
            action: Action::Delete,
            condition: None,
        },
        // Page up/down for scrolling
        KeyBinding {
            key: (KeyCode::PageUp, KeyModifiers::NONE),
            action: Action::PageUp,
            condition: None,
        },
        KeyBinding {
            key: (KeyCode::PageDown, KeyModifiers::NONE),
            action: Action::PageDown,
            condition: None,
        },
        // Ctrl+U: Clear input
        KeyBinding {
            key: (KeyCode::Char('u'), KeyModifiers::CONTROL),
            action: Action::Clear,
            condition: Some(ConditionAtom::InputNotEmpty),
        },
        // Ctrl+K: Delete to end
        KeyBinding {
            key: (KeyCode::Char('k'), KeyModifiers::CONTROL),
            action: Action::DeleteWord,
            condition: Some(ConditionAtom::InputNotEmpty),
        },
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_condition_evaluation_cursor_at_start() {
        let ctx = EvalContext {
            cursor_position: 0,
            input_width: 5,
            input_byte_len: 5,
            selected_index: 0,
            results_len: 10,
            original_input_empty: false,
        };

        assert!(ctx.evaluate(&ConditionAtom::CursorAtStart));
        assert!(!ctx.evaluate(&ConditionAtom::CursorAtEnd));
        assert!(!ctx.evaluate(&ConditionAtom::InputEmpty));
        assert!(ctx.evaluate(&ConditionAtom::InputNotEmpty));
        assert!(ctx.evaluate(&ConditionAtom::ListAtStart));
        assert!(ctx.evaluate(&ConditionAtom::HasResults));
        assert!(!ctx.evaluate(&ConditionAtom::NoResults));
    }

    #[test]
    fn test_condition_evaluation_cursor_at_end() {
        let ctx = EvalContext {
            cursor_position: 5,
            input_width: 5,
            input_byte_len: 5,
            selected_index: 0,
            results_len: 10,
            original_input_empty: false,
        };

        assert!(!ctx.evaluate(&ConditionAtom::CursorAtStart));
        assert!(ctx.evaluate(&ConditionAtom::CursorAtEnd));
    }

    #[test]
    fn test_keybinding_matches() {
        let binding = KeyBinding {
            key: (KeyCode::Char('c'), KeyModifiers::CONTROL),
            action: Action::Interrupt,
            condition: Some(ConditionAtom::InputNotEmpty),
        };

        assert!(binding.matches(KeyCode::Char('c'), KeyModifiers::CONTROL));
        assert!(!binding.matches(KeyCode::Char('c'), KeyModifiers::NONE));
    }
}
