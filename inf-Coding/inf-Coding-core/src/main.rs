use std::env;
use std::ffi::OsString;
use std::fs;
use std::io;
use std::path::{Path, PathBuf};
use std::process::{self, Command, Stdio};

#[derive(Clone, Debug)]
struct State {
    katala_allowed: bool,
    assist_mode: String, // "on" | "off"
    last_updated: String,
    updated_by: String,
}

impl Default for State {
    fn default() -> Self {
        Self {
            katala_allowed: false,
            assist_mode: "off".to_string(),
            last_updated: String::new(),
            updated_by: "unknown".to_string(),
        }
    }
}

fn main() {
    if let Err(e) = run() {
        eprintln!("{e}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        return Err(usage());
    }

    let exe_dir = exe_dir().map_err(|e| format!("[core] failed to resolve exe dir: {e}"))?;
    let inf_dir = exe_dir.parent().ok_or("[core] failed to resolve inf-Coding dir")?.to_path_buf();
    let katala_root = inf_dir.parent().ok_or("[core] failed to resolve Katala root")?.to_path_buf();

    match args[1].as_str() {
        "guard" => {
            guard(&inf_dir, &katala_root)?;
            println!("{}", katala_root.display());
        }
        "order-show" => {
            let state = load_state(&inf_dir).map_err(|e| format!("[order] {e}"))?;
            println!("KATALA_ALLOWED={}", if state.katala_allowed { 1 } else { 0 });
            println!("ASSIST_MODE={}", state.assist_mode);
            println!("LAST_UPDATED={}", state.last_updated);
            println!("UPDATED_BY={}", state.updated_by);
        }
        "order-set" => {
            if args.len() < 3 {
                return Err("Usage: order-set <clean|katala-off|katala-on|assist-off|assist-on>".to_string());
            }
            order_set(&inf_dir, &args[2])?;
        }
        "order-enforce" => {
            order_enforce(&inf_dir)?;
        }
        "katala-exec" => {
            let cmd = collect_command(&args[2..])?;
            guard(&inf_dir, &katala_root)?;
            order_enforce(&inf_dir)?;
            let code = run_command(&katala_root, cmd)?;
            process::exit(code);
        }
        "assist-exec" => {
            let cmd = collect_command(&args[2..])?;
            guard(&inf_dir, &katala_root)?;
            let state = load_state(&inf_dir).map_err(|e| format!("[assist-exec] {e}"))?;
            if state.assist_mode != "on" {
                return Err("[assist-exec] BLOCKED: require human order 'assist-on'.".to_string());
            }
            order_enforce(&inf_dir)?;
            let code = run_command(&katala_root, cmd)?;
            process::exit(code);
        }
        "open-shell" => {
            guard(&inf_dir, &katala_root)?;
            order_enforce(&inf_dir)?;
            let shell = env::var("SHELL").unwrap_or_else(|_| "/bin/bash".to_string());
            let status = Command::new(shell)
                .current_dir(&katala_root)
                .status()
                .map_err(|e| format!("[core] failed to launch shell: {e}"))?;
            process::exit(status.code().unwrap_or(1));
        }
        _ => return Err(usage()),
    }

    Ok(())
}

fn usage() -> String {
    "Usage: inf-coding-core <guard|order-show|order-set|order-enforce|katala-exec|assist-exec|open-shell> ...".to_string()
}

fn exe_dir() -> io::Result<PathBuf> {
    let exe = env::current_exe()?;
    Ok(exe.parent().unwrap_or(Path::new(".")).to_path_buf())
}

fn guard(inf_dir: &Path, katala_root: &Path) -> Result<(), String> {
    if !katala_root.join("src").is_dir() {
        return Err(format!("[guard] Katala ルートを検出できません: {}", katala_root.display()));
    }

    let caller = env::current_dir().map_err(|e| format!("[guard] failed to read current dir: {e}"))?;
    if !caller.starts_with(inf_dir) {
        return Err(format!(
            "[guard] NG: inf-Coding 経由で実行してください。\n[guard] 例: cd \"{}\" && ./open-katala.sh",
            inf_dir.display()
        ));
    }
    Ok(())
}

fn state_file(inf_dir: &Path) -> PathBuf {
    inf_dir.join("inf-Coding-Order").join("order-state.env")
}

fn load_state(inf_dir: &Path) -> Result<State, String> {
    let path = state_file(inf_dir);
    if !path.exists() {
        return Ok(State::default());
    }
    let text = fs::read_to_string(&path).map_err(|e| format!("failed to read {}: {e}", path.display()))?;
    let mut state = State::default();

    for line in text.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((k, v)) = line.split_once('=') else { continue };
        match k {
            "KATALA_ALLOWED" => state.katala_allowed = v.trim() == "1",
            "ASSIST_MODE" => state.assist_mode = v.trim().to_string(),
            "LAST_UPDATED" => state.last_updated = v.trim().to_string(),
            "UPDATED_BY" => state.updated_by = v.trim().to_string(),
            _ => {}
        }
    }

    if state.assist_mode != "on" {
        state.assist_mode = "off".to_string();
    }
    normalize_state(&mut state);
    Ok(state)
}

fn normalize_state(state: &mut State) {
    if state.assist_mode != "on" {
        state.assist_mode = "off".to_string();
        state.katala_allowed = false;
    }
}

fn save_state(inf_dir: &Path, state: &State) -> Result<(), String> {
    let path = state_file(inf_dir);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("failed to create {}: {e}", parent.display()))?;
    }

    let content = format!(
        "KATALA_ALLOWED={}\nASSIST_MODE={}\nLAST_UPDATED={}\nUPDATED_BY={}\n",
        if state.katala_allowed { 1 } else { 0 },
        state.assist_mode,
        state.last_updated,
        state.updated_by
    );
    fs::write(&path, content).map_err(|e| format!("failed to write {}: {e}", path.display()))
}

fn order_set(inf_dir: &Path, cmd: &str) -> Result<(), String> {
    let mut state = load_state(inf_dir).map_err(|e| format!("[order] {e}"))?;
    let now = iso_now().unwrap_or_default();
    state.updated_by = "human".to_string();

    match cmd {
        "clean" => {
            println!("[order] clean is deprecated (no cache/log subsystem).");
            return Ok(());
        }
        "katala-off" => {
            state.katala_allowed = false;
            state.last_updated = now;
            normalize_state(&mut state);
            save_state(inf_dir, &state).map_err(|e| format!("[order] {e}"))?;
            println!("[order] Katala usage: OFF");
        }
        "katala-on" => {
            state.katala_allowed = true;
            state.assist_mode = "on".to_string();
            state.last_updated = now;
            save_state(inf_dir, &state).map_err(|e| format!("[order] {e}"))?;
            println!("[order] Katala usage: ON (assist={})", state.assist_mode);
        }
        "assist-off" => {
            state.assist_mode = "off".to_string();
            state.katala_allowed = false;
            state.last_updated = now;
            save_state(inf_dir, &state).map_err(|e| format!("[order] {e}"))?;
            println!("[order] inf-Coding-Assist: OFF (katala={})", if state.katala_allowed { 1 } else { 0 });
        }
        "assist-on" => {
            state.assist_mode = "on".to_string();
            state.last_updated = now;
            save_state(inf_dir, &state).map_err(|e| format!("[order] {e}"))?;
            println!("[order] inf-Coding-Assist: ON");
        }
        _ => {
            return Err(format!("Unknown command: {cmd}\nUsage: order-set <clean|katala-off|katala-on|assist-off|assist-on>"));
        }
    }
    Ok(())
}

fn order_enforce(inf_dir: &Path) -> Result<(), String> {
    let state = load_state(inf_dir).map_err(|e| format!("[order] {e}"))?;

    if state.katala_allowed && state.assist_mode != "on" {
        return Err("[order] INVALID STATE: katala-on requires assist-on.".to_string());
    }

    if !state.katala_allowed {
        return Err("[order] Katala is DISABLED by human order (katala-off).".to_string());
    }

    Ok(())
}

fn collect_command(args: &[String]) -> Result<Vec<OsString>, String> {
    if args.is_empty() {
        return Err("Usage: <...-exec> <command...>".to_string());
    }
    Ok(args.iter().map(OsString::from).collect())
}

fn run_command(cwd: &Path, cmd: Vec<OsString>) -> Result<i32, String> {
    let mut iter = cmd.into_iter();
    let program = iter.next().ok_or("missing command")?;
    let status = Command::new(program)
        .args(iter)
        .current_dir(cwd)
        .stdin(Stdio::inherit())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .status()
        .map_err(|e| format!("failed to execute command: {e}"))?;
    Ok(status.code().unwrap_or(1))
}

fn iso_now() -> Option<String> {
    let output = Command::new("date").arg("-Is").output().ok()?;
    if !output.status.success() {
        return None;
    }
    String::from_utf8(output.stdout).ok().map(|s| s.trim().to_string())
}
