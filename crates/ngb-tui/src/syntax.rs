//! Syntax highlighting module using syntect
//!
//! Provides code syntax highlighting for code blocks in chat messages.
//! Based on bat's implementation.

use std::sync::LazyLock;
use syntect::easy::HighlightLines;
use syntect::highlighting::{Style, Theme, ThemeSet};
use syntect::parsing::SyntaxSet;

/// Default syntax set with common languages
pub static SYNTAX_SET: LazyLock<SyntaxSet> =
    LazyLock::new(SyntaxSet::load_defaults_newlines);

/// Default theme set (base16-ocean.dark)
pub static THEME_SET: LazyLock<ThemeSet> =
    LazyLock::new(ThemeSet::load_defaults);

/// Get the default theme for terminal
pub fn get_theme() -> &'static Theme {
    &THEME_SET.themes["base16-ocean.dark"]
}

/// Highlight code with syntax detection
///
/// Returns ANSI-escaped string suitable for terminal display
pub fn highlight_code(code: &str, language: &str) -> String {
    let syntax = SYNTAX_SET
        .find_syntax_by_token(language)
        .unwrap_or_else(|| SYNTAX_SET.find_syntax_plain_text());

    let theme = get_theme();
    let mut highlighter = HighlightLines::new(syntax, theme);

    let mut output = String::new();
    for line in code.lines() {
        let ranges: Vec<(Style, &str)> = highlighter.highlight_line(line, &SYNTAX_SET).unwrap_or_default();
        for (style, text) in ranges {
            // Convert syntect style to ANSI
            let ansi_style = style_to_ansi(style);
            output.push_str(&ansi_style);
            output.push_str(text);
            output.push_str("\x1b[0m"); // Reset
        }
        output.push('\n');
    }

    output
}

/// Convert syntect Style to ANSI escape sequence
fn style_to_ansi(style: Style) -> String {
    use syntect::highlighting::Color;

    let mut ansi = String::new();

    // Handle foreground color - Style stores Color directly, not Option
    let fg = style.foreground;
    if fg != Color::BLACK {
        let r = fg.r;
        let g = fg.g;
        let b = fg.b;

        if fg == Color::WHITE {
            ansi.push_str("\x1b[37m");
        } else if r == 0 && g == 0 && b > 0 {
            // Blues
            if b >= 200 {
                ansi.push_str("\x1b[34m");
            } else if b >= 100 {
                ansi.push_str("\x1b[94m");
            }
        } else if r == 0 && g > 0 && b == 0 {
            // Greens
            if g >= 200 {
                ansi.push_str("\x1b[32m");
            } else if g >= 100 {
                ansi.push_str("\x1b[92m");
            }
        } else if r > 0 && g == 0 && b == 0 {
            // Reds
            if r >= 200 {
                ansi.push_str("\x1b[31m");
            } else if r >= 100 {
                ansi.push_str("\x1b[91m");
            }
        } else if r > 0 && g > 0 && b == 0 {
            // Yellows
            if r >= 200 && g >= 200 {
                ansi.push_str("\x1b[33m");
            } else if r >= 100 && g >= 100 {
                ansi.push_str("\x1b[93m");
            }
        } else {
            // RGB color (24-bit)
            ansi.push_str(&format!("\x1b[38;2;{};{};{}m", r, g, b));
        }
    }

    // Handle bold
    if style.font_style.contains(syntect::highlighting::FontStyle::BOLD) {
        ansi.push_str("\x1b[1m");
    }

    // Handle italic
    if style.font_style.contains(syntect::highlighting::FontStyle::ITALIC) {
        ansi.push_str("\x1b[3m");
    }

    // Handle underline
    if style.font_style.contains(syntect::highlighting::FontStyle::UNDERLINE) {
        ansi.push_str("\x1b[4m");
    }

    ansi
}
