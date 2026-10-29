const express = require("express");
const { Pool } = require("pg");
const cors = require("cors");

const app = express();
app.use(cors());
app.use(express.json());

const pool = new Pool({
  user: process.env.POSTGRES_USER || "se_user",
  host: process.env.POSTGRES_HOST || "postgres",
  database: process.env.POSTGRES_DB || "se_hw5",
  password: process.env.POSTGRES_PASSWORD || "se_password",
  port: Number(process.env.POSTGRES_PORT) || 5432,
});

app.get("/health", (req, res) => {
  res.json({ status: "ok", service: "node-api", timestamp: new Date().toISOString() });
});

app.get("/services", async (req, res) => {
  try {
    const result = await pool.query("SELECT * FROM services ORDER BY id ASC");
    res.json({ services: result.rows });
  } catch (err) {
    res.status(500).json({ error: "database_error", message: err.message });
  }
});

app.get("/", (req, res) => {
  res.json({ message: "Node.js API for HW5 Docker Microservices", endpoints: ["/health", "/services"] });
});

const port = process.env.PORT || 3000;
app.listen(port, () => {
  console.log(`node-api running on port ${port}`);
});
