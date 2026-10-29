use actix_web::{get, web, App, HttpResponse, HttpServer, Responder};
use serde::Serialize;
use std::env;

#[derive(Serialize)]
struct Health {
    status: String,
    service: String,
    timestamp: String,
}

#[get("/health")]
async fn health() -> impl Responder {
    HttpResponse::Ok().json(Health {
        status: "ok".to_string(),
        service: "rust-api".to_string(),
        timestamp: chrono::Utc::now().to_rfc3339(),
    })
}

#[get("/")]
async fn root() -> impl Responder {
    HttpResponse::Ok().json(serde_json::json!({
        "message": "Rust API for HW5 Docker Microservices",
        "endpoints": ["/health"]
    }))
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let port: u16 = env::var("PORT").unwrap_or_else(|_| "8081".to_string()).parse().expect("PORT must be number");
    println!("rust-api running on port {}", port);
    HttpServer::new(|| {
        App::new()
            .service(health)
            .service(root)
    })
    .bind(("0.0.0.0", port))?
    .run()
    .await
}
