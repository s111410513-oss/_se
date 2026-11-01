use axum::{
    extract::{Path, State},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post, delete},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::{sync::{Arc, Mutex}};
use tower_http::services::ServeDir;

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct Task {
    pub id: u64,
    pub title: String,
    pub completed: bool,
}

#[derive(Debug, Deserialize)]
pub struct CreateTask {
    pub title: String,
}

#[derive(Clone, Default)]
pub struct AppState {
    tasks: Arc<Mutex<Vec<Task>>>,
    next_id: Arc<Mutex<u64>>,
}

pub fn validate_title(title: &str) -> Result<String, &'static str> {
    let cleaned = title.trim();
    if cleaned.is_empty() {
        return Err("待辦事項不能為空");
    }
    if cleaned.chars().count() > 80 {
        return Err("待辦事項不可超過 80 個字");
    }
    Ok(cleaned.to_string())
}

impl AppState {
    pub fn create_task(&self, title: &str) -> Result<Task, &'static str> {
        let title = validate_title(title)?;
        let mut next_id = self.next_id.lock().expect("id lock poisoned");
        let task = Task { id: *next_id, title, completed: false };
        *next_id += 1;
        self.tasks.lock().expect("tasks lock poisoned").push(task.clone());
        Ok(task)
    }

    pub fn list_tasks(&self) -> Vec<Task> {
        self.tasks.lock().expect("tasks lock poisoned").clone()
    }

    pub fn toggle_task(&self, id: u64) -> Option<Task> {
        let mut tasks = self.tasks.lock().expect("tasks lock poisoned");
        let task = tasks.iter_mut().find(|task| task.id == id)?;
        task.completed = !task.completed;
        Some(task.clone())
    }

    pub fn delete_task(&self, id: u64) -> bool {
        let mut tasks = self.tasks.lock().expect("tasks lock poisoned");
        let old_len = tasks.len();
        tasks.retain(|task| task.id != id);
        tasks.len() != old_len
    }
}

async fn health() -> &'static str { "ok" }

async fn list_tasks(State(state): State<AppState>) -> Json<Vec<Task>> {
    Json(state.list_tasks())
}

async fn create_task(
    State(state): State<AppState>,
    Json(payload): Json<CreateTask>,
) -> impl IntoResponse {
    match state.create_task(&payload.title) {
        Ok(task) => (StatusCode::CREATED, Json(task)).into_response(),
        Err(message) => (StatusCode::BAD_REQUEST, Json(serde_json::json!({"error": message}))).into_response(),
    }
}

async fn toggle_task(State(state): State<AppState>, Path(id): Path<u64>) -> impl IntoResponse {
    match state.toggle_task(id) {
        Some(task) => (StatusCode::OK, Json(task)).into_response(),
        None => (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "找不到待辦事項"}))).into_response(),
    }
}

async fn delete_task(State(state): State<AppState>, Path(id): Path<u64>) -> impl IntoResponse {
    if state.delete_task(id) {
        StatusCode::NO_CONTENT.into_response()
    } else {
        (StatusCode::NOT_FOUND, Json(serde_json::json!({"error": "找不到待辦事項"}))).into_response()
    }
}

pub fn app() -> Router {
    let state = AppState::default();
    Router::new()
        .route("/api/health", get(health))
        .route("/api/tasks", get(list_tasks).post(create_task))
        .route("/api/tasks/:id/toggle", post(toggle_task))
        .route("/api/tasks/:id", delete(delete_task))
        .nest_service("/", ServeDir::new("web").append_index_html_on_directories(true))
        .with_state(state)
}

#[cfg(test)]
mod unit_tests {
    use super::*;

    #[test]
    fn title_is_trimmed() {
        assert_eq!(validate_title("  讀書  ").unwrap(), "讀書");
    }

    #[test]
    fn empty_title_is_rejected() {
        assert_eq!(validate_title("   "), Err("待辦事項不能為空"));
    }

    #[test]
    fn title_over_80_characters_is_rejected() {
        assert_eq!(validate_title(&"a".repeat(81)), Err("待辦事項不可超過 80 個字"));
    }

    #[test]
    fn create_task_assigns_id_and_default_status() {
        let state = AppState::default();
        let task = state.create_task("完成作業").unwrap();
        assert_eq!(task.id, 1);
        assert!(!task.completed);
    }

    #[test]
    fn toggle_changes_status() {
        let state = AppState::default();
        let task = state.create_task("測試").unwrap();
        assert!(state.toggle_task(task.id).unwrap().completed);
        assert!(!state.toggle_task(task.id).unwrap().completed);
    }

    #[test]
    fn delete_removes_existing_task() {
        let state = AppState::default();
        let task = state.create_task("刪除我").unwrap();
        assert!(state.delete_task(task.id));
        assert!(state.list_tasks().is_empty());
        assert!(!state.delete_task(task.id));
    }
}
