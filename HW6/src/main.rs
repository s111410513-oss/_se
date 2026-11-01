use hw6_task_board::app;
use std::net::SocketAddr;

#[tokio::main]
async fn main() {
    let app = app();
    let addr = SocketAddr::from(([127, 0, 0, 1], 3000));
    println!("HW6 Task Board is running at http://{addr}");
    let listener = tokio::net::TcpListener::bind(addr).await.expect("failed to bind port 3000");
    axum::serve(listener, app).await.expect("server error");
}
