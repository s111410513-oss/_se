FROM rust:1.80-slim AS builder
WORKDIR /app
COPY Cargo.toml ./
RUN mkdir src && echo 'fn main(){}' > src/main.rs && cargo build --release && rm -rf src
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=builder /app/target/release/rust-api /app/rust-api
EXPOSE 8081
ENV PORT=8081
CMD ["./rust-api"]
