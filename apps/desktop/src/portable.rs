//! Fork-only Windows portable edition detection and layout constants.
use std::path::{Path, PathBuf};

pub const MARKER: &str = "portable.marker";
pub const DATA_DIR: &str = "data";
pub const APP_ID: &str = "org.wenyi.desktop.portable";

pub fn marker_path(install: &Path) -> PathBuf {
    install.join(MARKER)
}

pub fn enabled_at(install: &Path) -> bool {
    marker_path(install).is_file()
}

pub fn enabled() -> bool {
    cfg!(windows)
        && crate::paths::running_install_dir().is_ok_and(|directory| enabled_at(&directory))
}

pub fn data_root(install: &Path) -> PathBuf {
    install.join(DATA_DIR)
}

pub fn engine_args(portable: bool) -> &'static [&'static str] {
    if portable { &["--portable"] } else { &[] }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::path::Path;

    fn temp_dir(name: &str) -> std::path::PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "wenyi-portable-{name}-{}",
            std::process::id()
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn marker_must_be_a_regular_file() {
        let install = temp_dir("marker");
        assert!(!enabled_at(&install));
        fs::create_dir_all(install.join(MARKER)).unwrap();
        assert!(!enabled_at(&install));
        fs::remove_dir_all(install.join(MARKER)).unwrap();
        fs::write(install.join(MARKER), "portable").unwrap();
        assert!(enabled_at(&install));
        fs::remove_dir_all(install).unwrap();
    }

    #[test]
    fn data_root_is_the_fixed_data_child() {
        assert_eq!(
            data_root(Path::new("/apps/wenyi")),
            Path::new("/apps/wenyi/data")
        );
    }

    #[test]
    fn the_engine_receives_the_portable_flag_only_in_portable_mode() {
        assert_eq!(engine_args(true), &["--portable"]);
        assert!(engine_args(false).is_empty());
    }
}
