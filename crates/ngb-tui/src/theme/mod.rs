//! Theme system for NGB Shell TUI

use ratatui::style::Color;

/// Available theme presets
#[derive(Debug, Clone, Copy, PartialEq, Default)]
pub enum ThemeName {
    #[default]
    CatppuccinMocha,
    CatppuccinLatte,
    Kanagawa,
    RosePine,
    RosePineDawn,
    TokyoNight,
    Midnight,
    Terminal,
}

/// Icon set for UI elements
#[derive(Debug, Clone)]
pub struct IconSet {
    /// User message prefix
    pub user: &'static str,
    /// Agent/Robot message prefix
    pub agent: &'static str,
    /// System message prefix
    pub system: &'static str,
    /// Thinking/spinner animation frames
    pub spinner: [&'static str; 10],
    /// Tool running indicator
    pub tool_running: &'static str,
    /// Tool success indicator
    pub tool_success: &'static str,
    /// Tool error indicator
    pub tool_error: &'static str,
    /// Bullet point
    pub bullet: &'static str,
    /// Arrow (for tool calls)
    pub arrow: &'static str,
    /// Checkmark
    pub check: &'static str,
    /// Cross/X mark
    pub cross: &'static str,
    /// Info icon
    pub info: &'static str,
    /// Warning icon
    pub warning: &'static str,
    /// Lock icon (for secure)
    pub lock: &'static str,
    /// Code block delimiter
    pub code_block: &'static str,
}

impl Default for IconSet {
    fn default() -> Self {
        Self::modern()
    }
}

impl IconSet {
    /// Modern Unicode icons (default)
    pub fn modern() -> Self {
        Self {
            user: "👤",
            agent: "🤖",
            system: "ℹ️",
            spinner: ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
            tool_running: "⚙",
            tool_success: "✓",
            tool_error: "✗",
            bullet: "•",
            arrow: "→",
            check: "✓",
            cross: "✗",
            info: "ℹ",
            warning: "⚠",
            lock: "🔒",
            code_block: "```",
        }
    }

    /// Minimal ASCII icons (fallback)
    pub fn minimal() -> Self {
        Self {
            user: ">",
            agent: "#",
            system: "!",
            spinner: ["|", "/", "-", "\\", "|", "/", "-", "\\", "|", "/"],
            tool_running: "*",
            tool_success: "+",
            tool_error: "x",
            bullet: "-",
            arrow: "->",
            check: "[+]",
            cross: "[x]",
            info: "i",
            warning: "!",
            lock: "[=]",
            code_block: "```",
        }
    }

    /// Box drawing characters (retro terminal)
    pub fn box_drawing() -> Self {
        Self {
            user: "│",
            agent: "▣",
            system: "◉",
            spinner: ["◐", "◑", "◒", "◓", "◐", "◑", "◒", "◓", "◐", "◑"],
            tool_running: "◌",
            tool_success: "◉",
            tool_error: "✕",
            bullet: "▪",
            arrow: "▶",
            check: "☑",
            cross: "☒",
            info: "ℹ",
            warning: "⚠",
            lock: "◈",
            code_block: "┄┄┄",
        }
    }

    /// Cute animal icons
    pub fn cute() -> Self {
        Self {
            user: "🧑",
            agent: "🤖",
            system: "📢",
            spinner: ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘", "🌑", "🌚"],
            tool_running: "🔧",
            tool_success: "✅",
            tool_error: "❌",
            bullet: "◇",
            arrow: "➜",
            check: "✅",
            cross: "❌",
            info: "💡",
            warning: "⚡",
            lock: "🔐",
            code_block: "───",
        }
    }
}

/// Theme colors for NGB Shell
#[derive(Debug, Clone)]
pub struct Theme {
    pub name: ThemeName,
    pub icons: IconSet,
    pub background: Color,
    pub foreground: Color,
    pub accent: Color,
    pub success: Color,
    pub warning: Color,
    pub error: Color,
    pub secondary: Color,
    pub bubble: Color,
    pub code_background: Color,
    // Semantic colors
    pub user_message: Color,
    pub agent_message: Color,
    pub thinking: Color,
    pub tool_running: Color,
    pub tool_success: Color,
    pub tool_error: Color,
    pub border: Color,
    pub input: Color,
    pub status: Color,
}

impl Theme {
    /// Get a theme by name
    pub fn from_name(name: ThemeName) -> Self {
        match name {
            ThemeName::CatppuccinMocha => Self::catppuccin_mocha(),
            ThemeName::CatppuccinLatte => Self::catppuccin_latte(),
            ThemeName::Kanagawa => Self::kanagawa(),
            ThemeName::RosePine => Self::rose_pine(),
            ThemeName::RosePineDawn => Self::rose_pine_dawn(),
            ThemeName::TokyoNight => Self::tokyo_night(),
            ThemeName::Midnight => Self::midnight(),
            ThemeName::Terminal => Self::terminal(),
        }
    }

    /// Catppuccin Mocha (default) - Soft pastel, dark
    fn catppuccin_mocha() -> Self {
        Self {
            name: ThemeName::CatppuccinMocha,
            icons: IconSet::default(),
            background: Color::Rgb(0x1e, 0x1e, 0x2e),
            foreground: Color::Rgb(0xcd, 0xd6, 0xf4),
            accent: Color::Rgb(0x89, 0xb4, 0xfa),
            success: Color::Rgb(0xa6, 0xe3, 0xa1),
            warning: Color::Rgb(0xf9, 0xe2, 0xaf),
            error: Color::Rgb(0xf3, 0x8b, 0xa8),
            secondary: Color::Rgb(0x6c, 0x70, 0x86),
            bubble: Color::Rgb(0x45, 0x47, 0x5a),
            code_background: Color::Rgb(0x18, 0x18, 0x25),
            user_message: Color::Rgb(0x94, 0xe2, 0xd5),
            agent_message: Color::Rgb(0xa6, 0xe3, 0xa1),
            thinking: Color::Rgb(0xf9, 0xe2, 0xaf),
            tool_running: Color::Rgb(0xf9, 0xe2, 0xaf),
            tool_success: Color::Rgb(0xa6, 0xe3, 0xa1),
            tool_error: Color::Rgb(0xf3, 0x8b, 0xa8),
            border: Color::Rgb(0x6c, 0x70, 0x86),
            input: Color::Rgb(0xcd, 0xd6, 0xf4),
            status: Color::Rgb(0x6c, 0x70, 0x86),
        }
    }

    /// Catppuccin Latte - Soft pastel, light
    fn catppuccin_latte() -> Self {
        Self {
            name: ThemeName::CatppuccinLatte,
            icons: IconSet::default(),
            background: Color::Rgb(0xef, 0xf1, 0xf5),
            foreground: Color::Rgb(0x4c, 0x4f, 0x69),
            accent: Color::Rgb(0x04, 0x0a, 0xe3),
            success: Color::Rgb(0x40, 0xa0, 0x2e),
            warning: Color::Rgb(0xdf, 0x8e, 0x1d),
            error: Color::Rgb(0xd2, 0x0f, 0x2f),
            secondary: Color::Rgb(0x6c, 0x6f, 0x85),
            bubble: Color::Rgb(0xe6, 0xe9, 0xef),
            code_background: Color::Rgb(0xdc, 0xda, 0xe3),
            user_message: Color::Rgb(0x1e, 0x66, 0x98),
            agent_message: Color::Rgb(0x40, 0xa0, 0x2e),
            thinking: Color::Rgb(0xdf, 0x8e, 0x1d),
            tool_running: Color::Rgb(0xdf, 0x8e, 0x1d),
            tool_success: Color::Rgb(0x40, 0xa0, 0x2e),
            tool_error: Color::Rgb(0xd2, 0x0f, 0x2f),
            border: Color::Rgb(0xcc, 0xd0, 0xda),
            input: Color::Rgb(0x4c, 0x4f, 0x69),
            status: Color::Rgb(0x6c, 0x6f, 0x85),
        }
    }

    /// Kanagawa - Ukiyo-e style, indigo/gold
    fn kanagawa() -> Self {
        Self {
            name: ThemeName::Kanagawa,
            icons: IconSet::default(),
            background: Color::Rgb(0x1f, 0x1f, 0x28),
            foreground: Color::Rgb(0xc8, 0xc8, 0xc0),
            accent: Color::Rgb(0x7e, 0xa0, 0xcb),
            success: Color::Rgb(0x86, 0x9c, 0x76),
            warning: Color::Rgb(0xde, 0xc9, 0x7c),
            error: Color::Rgb(0xc4, 0x7a, 0x7c),
            secondary: Color::Rgb(0x7e, 0x88, 0x96),
            bubble: Color::Rgb(0x2a, 0x2a, 0x35),
            code_background: Color::Rgb(0x18, 0x18, 0x20),
            user_message: Color::Rgb(0x7e, 0xa0, 0xcb),
            agent_message: Color::Rgb(0x86, 0x9c, 0x76),
            thinking: Color::Rgb(0xde, 0xc9, 0x7c),
            tool_running: Color::Rgb(0xde, 0xc9, 0x7c),
            tool_success: Color::Rgb(0x86, 0x9c, 0x76),
            tool_error: Color::Rgb(0xc4, 0x7a, 0x7c),
            border: Color::Rgb(0x3e, 0x42, 0x52),
            input: Color::Rgb(0xc8, 0xc8, 0xc0),
            status: Color::Rgb(0x7e, 0x88, 0x96),
        }
    }

    /// Rose Pine - Soft dark
    fn rose_pine() -> Self {
        Self {
            name: ThemeName::RosePine,
            icons: IconSet::default(),
            background: Color::Rgb(0x19, 0x17, 0x1f),
            foreground: Color::Rgb(0xe0, 0xde, 0xdf),
            accent: Color::Rgb(0xc4, 0x69, 0x7d),
            success: Color::Rgb(0x9c, 0xce, 0x8b),
            warning: Color::Rgb(0xeb, 0xbc, 0x2f),
            error: Color::Rgb(0xeb, 0x6b, 0x6f),
            secondary: Color::Rgb(0x77, 0x6a, 0x85),
            bubble: Color::Rgb(0x2a, 0x28, 0x31),
            code_background: Color::Rgb(0x10, 0x0e, 0x14),
            user_message: Color::Rgb(0xeb, 0xbc, 0x2f),
            agent_message: Color::Rgb(0x9c, 0xce, 0x8b),
            thinking: Color::Rgb(0xeb, 0xbc, 0x2f),
            tool_running: Color::Rgb(0xeb, 0xbc, 0x2f),
            tool_success: Color::Rgb(0x9c, 0xce, 0x8b),
            tool_error: Color::Rgb(0xeb, 0x6b, 0x6f),
            border: Color::Rgb(0x3b, 0x38, 0x45),
            input: Color::Rgb(0xe0, 0xde, 0xdf),
            status: Color::Rgb(0x77, 0x6a, 0x85),
        }
    }

    /// Rose Pine Dawn - Soft light
    fn rose_pine_dawn() -> Self {
        Self {
            name: ThemeName::RosePineDawn,
            icons: IconSet::default(),
            background: Color::Rgb(0xfa, 0xf4, 0xed),
            foreground: Color::Rgb(0x4a, 0x45, 0x58),
            accent: Color::Rgb(0xd0, 0x72, 0x7c),
            success: Color::Rgb(0x31, 0x6f, 0x3e),
            warning: Color::Rgb(0xd4, 0x8a, 0x1c),
            error: Color::Rgb(0xdf, 0x5d, 0x63),
            secondary: Color::Rgb(0x83, 0x7a, 0x8f),
            bubble: Color::Rgb(0xeb, 0xe5, 0xde),
            code_background: Color::Rgb(0xe3, 0xdb, 0xd5),
            user_message: Color::Rgb(0xd0, 0x72, 0x7c),
            agent_message: Color::Rgb(0x31, 0x6f, 0x3e),
            thinking: Color::Rgb(0xd4, 0x8a, 0x1c),
            tool_running: Color::Rgb(0xd4, 0x8a, 0x1c),
            tool_success: Color::Rgb(0x31, 0x6f, 0x3e),
            tool_error: Color::Rgb(0xdf, 0x5d, 0x63),
            border: Color::Rgb(0xd4, 0xcc, 0xc5),
            input: Color::Rgb(0x4a, 0x45, 0x58),
            status: Color::Rgb(0x83, 0x7a, 0x8f),
        }
    }

    /// Tokyo Night - Classic dark blue
    fn tokyo_night() -> Self {
        Self {
            name: ThemeName::TokyoNight,
            icons: IconSet::default(),
            background: Color::Rgb(0x1a, 0x1b, 0x26),
            foreground: Color::Rgb(0xa9, 0xb1, 0xd6),
            accent: Color::Rgb(0x7a, 0xac, 0xe3),
            success: Color::Rgb(0x9e, 0xd6, 0x69),
            warning: Color::Rgb(0xe0, 0xaf, 0x68),
            error: Color::Rgb(0xf7, 0x76, 0x8e),
            secondary: Color::Rgb(0x56, 0x5f, 0x6e),
            bubble: Color::Rgb(0x24, 0x25, 0x32),
            code_background: Color::Rgb(0x16, 0x16, 0x20),
            user_message: Color::Rgb(0x7a, 0xac, 0xe3),
            agent_message: Color::Rgb(0x9e, 0xd6, 0x69),
            thinking: Color::Rgb(0xe0, 0xaf, 0x68),
            tool_running: Color::Rgb(0xe0, 0xaf, 0x68),
            tool_success: Color::Rgb(0x9e, 0xd6, 0x69),
            tool_error: Color::Rgb(0xf7, 0x76, 0x8e),
            border: Color::Rgb(0x36, 0x3f, 0x52),
            input: Color::Rgb(0xa9, 0xb1, 0xd6),
            status: Color::Rgb(0x56, 0x5f, 0x6e),
        }
    }

    /// Midnight - Pure black, high contrast
    fn midnight() -> Self {
        Self {
            name: ThemeName::Midnight,
            icons: IconSet::default(),
            background: Color::Rgb(0x00, 0x00, 0x00),
            foreground: Color::Rgb(0xee, 0xee, 0xee),
            accent: Color::Rgb(0x00, 0x7f, 0xff),
            success: Color::Rgb(0x00, 0xff, 0x00),
            warning: Color::Rgb(0xff, 0xff, 0x00),
            error: Color::Rgb(0xff, 0x00, 0x00),
            secondary: Color::Rgb(0x80, 0x80, 0x80),
            bubble: Color::Rgb(0x20, 0x20, 0x20),
            code_background: Color::Rgb(0x10, 0x10, 0x10),
            user_message: Color::Rgb(0x00, 0x7f, 0xff),
            agent_message: Color::Rgb(0x00, 0xff, 0x00),
            thinking: Color::Rgb(0xff, 0xff, 0x00),
            tool_running: Color::Rgb(0xff, 0xff, 0x00),
            tool_success: Color::Rgb(0x00, 0xff, 0x00),
            tool_error: Color::Rgb(0xff, 0x00, 0x00),
            border: Color::Rgb(0x40, 0x40, 0x40),
            input: Color::Rgb(0xee, 0xee, 0xee),
            status: Color::Rgb(0x80, 0x80, 0x80),
        }
    }

    /// Terminal - Follow terminal 16 colors
    fn terminal() -> Self {
        Self {
            name: ThemeName::Terminal,
            icons: IconSet::minimal(),
            background: Color::Reset,
            foreground: Color::Reset,
            accent: Color::Blue,
            success: Color::Green,
            warning: Color::Yellow,
            error: Color::Red,
            secondary: Color::DarkGray,
            bubble: Color::DarkGray,
            code_background: Color::Black,
            user_message: Color::Cyan,
            agent_message: Color::Green,
            thinking: Color::Yellow,
            tool_running: Color::Yellow,
            tool_success: Color::Green,
            tool_error: Color::Red,
            border: Color::DarkGray,
            input: Color::Reset,
            status: Color::DarkGray,
        }
    }
}

impl Default for Theme {
    fn default() -> Self {
        Self::catppuccin_mocha()
    }
}

/// Get all available theme names
pub fn all_theme_names() -> Vec<ThemeName> {
    vec![
        ThemeName::CatppuccinMocha,
        ThemeName::CatppuccinLatte,
        ThemeName::Kanagawa,
        ThemeName::RosePine,
        ThemeName::RosePineDawn,
        ThemeName::TokyoNight,
        ThemeName::Midnight,
        ThemeName::Terminal,
    ]
}

/// Get theme name display string
pub fn theme_display_name(name: ThemeName) -> &'static str {
    match name {
        ThemeName::CatppuccinMocha => "Catppuccin Mocha",
        ThemeName::CatppuccinLatte => "Catppuccin Latte",
        ThemeName::Kanagawa => "Kanagawa",
        ThemeName::RosePine => "Rose Pine",
        ThemeName::RosePineDawn => "Rose Pine Dawn",
        ThemeName::TokyoNight => "Tokyo Night",
        ThemeName::Midnight => "Midnight",
        ThemeName::Terminal => "Terminal",
    }
}
