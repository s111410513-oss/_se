use axum::{body::Body, http::{Request, StatusCode}};
use http_body_util::BodyExt;
use serde_json::{json, Value};
use tower::ServiceExt;
use hw6_task_board::app;

async fn response_json(response: axum::response::Response) -> Value {
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    serde_json::from_slice(&bytes).unwrap()
}

#[tokio::test]
async fn health_endpoint_returns_ok() {
    let response = app().oneshot(Request::builder().uri("/api/health").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(response.status(), StatusCode::OK);
}

#[tokio::test]
async fn create_and_list_tasks_through_api() {
    let app = app();
    let response = app.clone().oneshot(
        Request::builder().method("POST").uri("/api/tasks")
            .header("content-type", "application/json")
            .body(Body::from(json!({"title":"準備考試"}).to_string())).unwrap()
    ).await.unwrap();
    assert_eq!(response.status(), StatusCode::CREATED);
    let created = response_json(response).await;
    assert_eq!(created["title"], "準備考試");
    assert_eq!(created["completed"], false);

    let response = app.oneshot(Request::builder().uri("/api/tasks").body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    let tasks = response_json(response).await;
    assert_eq!(tasks.as_array().unwrap().len(), 1);
}

#[tokio::test]
async fn invalid_task_returns_bad_request() {
    let response = app().oneshot(
        Request::builder().method("POST").uri("/api/tasks")
            .header("content-type", "application/json")
            .body(Body::from(json!({"title":"  "}).to_string())).unwrap()
    ).await.unwrap();
    assert_eq!(response.status(), StatusCode::BAD_REQUEST);
}

#[tokio::test]
async fn toggle_and_delete_task_through_api() {
    let app = app();
    let response = app.clone().oneshot(
        Request::builder().method("POST").uri("/api/tasks")
            .header("content-type", "application/json")
            .body(Body::from(json!({"title":"要完成的事情"}).to_string())).unwrap()
    ).await.unwrap();
    let task = response_json(response).await;
    let id = task["id"].as_u64().unwrap();

    let response = app.clone().oneshot(Request::builder().method("POST").uri(format!("/api/tasks/{id}/toggle")).body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(response.status(), StatusCode::OK);
    assert_eq!(response_json(response).await["completed"], true);

    let response = app.oneshot(Request::builder().method("DELETE").uri(format!("/api/tasks/{id}")).body(Body::empty()).unwrap()).await.unwrap();
    assert_eq!(response.status(), StatusCode::NO_CONTENT);
}
