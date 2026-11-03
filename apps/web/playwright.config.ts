import { defineConfig } from "@playwright/test";

const PORT = 8799;

// Runs against the real production shape: the FastAPI process serving the static export.
export default defineConfig({
  testDir: "./e2e",
  outputDir: "./e2e/results",
  use: { baseURL: `http://127.0.0.1:${PORT}` },
  webServer: {
    command: "rm -rf .e2e-data && uv run simulacra up",
    cwd: "../..",
    url: `http://127.0.0.1:${PORT}/api/v1/health`,
    reuseExistingServer: false,
    env: {
      SIMULACRA_PORT: String(PORT),
      SIMULACRA_DATA_DIR: ".e2e-data",
      SIMULACRA_ENABLE_MOCK_BACKEND: "true",
    },
  },
});
