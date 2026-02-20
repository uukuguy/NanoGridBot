use std::path::Path;

use regex::Regex;

/// Validate that a container path is safe (no escape attempts).
pub fn validate_container_path(container_path: &str) -> bool {
    // Check absolute paths
    if container_path.starts_with('/') {
        let safe_prefixes = ["/workspace", "/home", "/tmp", "/app"];
        if !safe_prefixes.iter().any(|p| container_path.starts_with(p)) {
            return false;
        }
    }

    // No parent directory references
    if container_path.contains("..") {
        return false;
    }

    // No special device paths
    if container_path.starts_with("/dev") || container_path.starts_with("/proc") {
        return false;
    }

    true
}

/// Sanitize a filename to prevent path traversal.
pub fn sanitize_filename(filename: &str) -> String {
    // Extract just the file name component
    let name = Path::new(filename)
        .file_name()
        .map(|n| n.to_string_lossy().to_string())
        .unwrap_or_default();

    // Remove dangerous characters (keep word chars, spaces, hyphens, dots)
    let re = Regex::new(r"[^\w\s\-.]").unwrap();
    let sanitized = re.replace_all(&name, "").to_string();

    // Limit length
    if sanitized.len() > 255 {
        sanitized[..255].to_string()
    } else {
        sanitized
    }
}

/// Check for path traversal attempts.
pub fn check_path_traversal(path: &str) -> bool {
    // Returns true if path traversal is detected
    path.contains("..") || path.contains('\0')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validate_safe_container_paths() {
        assert!(validate_container_path("workspace/code"));
        assert!(validate_container_path("/workspace/code"));
        assert!(validate_container_path("/home/user/data"));
        assert!(validate_container_path("/tmp/output"));
        assert!(validate_container_path("/app/config"));
    }

    #[test]
    fn validate_unsafe_container_paths() {
        assert!(!validate_container_path("/etc/passwd"));
        assert!(!validate_container_path("/root/.ssh"));
        assert!(!validate_container_path("../escape"));
        assert!(!validate_container_path("/workspace/../etc"));
        assert!(!validate_container_path("/dev/sda"));
        assert!(!validate_container_path("/proc/1/environ"));
    }

    #[test]
    fn sanitize_normal_filename() {
        assert_eq!(sanitize_filename("report.txt"), "report.txt");
        assert_eq!(sanitize_filename("my-file.pdf"), "my-file.pdf");
    }

    #[test]
    fn sanitize_path_traversal() {
        assert_eq!(sanitize_filename("../../etc/passwd"), "passwd");
        assert_eq!(sanitize_filename("/absolute/path/file.txt"), "file.txt");
    }

    #[test]
    fn sanitize_special_characters() {
        let result = sanitize_filename("file<>name|with:bad*chars.txt");
        assert!(!result.contains('<'));
        assert!(!result.contains('>'));
        assert!(!result.contains('|'));
        assert!(!result.contains('*'));
    }

    #[test]
    fn sanitize_long_filename() {
        let long_name = "a".repeat(300);
        let result = sanitize_filename(&long_name);
        assert!(result.len() <= 255);
    }

    #[test]
    fn check_path_traversal_detection() {
        assert!(check_path_traversal("../secret"));
        assert!(check_path_traversal("dir/../../etc"));
        assert!(check_path_traversal("file\0.txt"));
        assert!(!check_path_traversal("normal/path/file.txt"));
    }
}
