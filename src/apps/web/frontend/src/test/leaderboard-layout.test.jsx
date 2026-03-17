import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

test("leaderboard styles contain overflow within the table region on narrow screens", () => {
  const stylesheetPath = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "../styles.css"
  );
  const stylesheet = readFileSync(stylesheetPath, "utf8");

  expect(stylesheet).toContain(".table-wrap {");
  expect(stylesheet).toContain("max-width: 100%;");
  expect(stylesheet).toContain("overflow-x: auto;");
  expect(stylesheet).toContain(".panel {");
  expect(stylesheet).toContain("min-width: 0;");
});
