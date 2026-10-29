CREATE TABLE IF NOT EXISTS services (
  id SERIAL PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  type VARCHAR(50) NOT NULL,
  description TEXT,
  port INTEGER
);

INSERT INTO services (name, type, description, port) VALUES
  ('nginx', 'webserver/reverse-proxy', '統一入口，負責路由與靜態網頁', 80),
  ('postgres', 'database', 'PostgreSQL 關聯式資料庫', 5432),
  ('node-api', 'microservice', 'Node.js + Express REST API', 3000),
  ('rust-api', 'microservice', 'Rust + Actix Web REST API', 8081),
  ('python-api', 'microservice', 'Python + Flask REST API', 5000),
  ('web', 'frontend', '簡易 HTML/JS 展示介面', 80)
ON CONFLICT DO NOTHING;
