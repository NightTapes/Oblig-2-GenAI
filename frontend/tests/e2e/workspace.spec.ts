import { test, expect } from "@playwright/test";
import path from "node:path";

test("CSV → profile → charts → explorer → model-offline recovery", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByText("Backend connected")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "From data to discovery." }),
  ).toBeVisible();
  await page
    .getByLabel("Upload CSV", { exact: true })
    .setInputFiles(path.resolve("../sample_data/plant_growth_synthetic.csv"));
  await expect(
    page.getByRole("heading", { name: "plant growth synthetic", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Total observations", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".chart-card")).toHaveCount(4);
  await expect(page.locator(".echart canvas").first()).toBeVisible();
  // Manual chart creation works without AI.
  await page.getByRole("button", { name: "Create chart", exact: true }).click();
  await page.getByLabel("Chart type").selectOption("bar");
  await page.getByLabel("X axis / group").selectOption("treatment_group");
  await page
    .getByLabel("Measurement (optional for count)")
    .selectOption("plant_height_cm");
  await page
    .getByLabel("Chart title (optional)")
    .fill("Average growth by treatment");
  await page.getByRole("button", { name: "Add to workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Average growth by treatment" }),
  ).toBeVisible();
  for (const type of ["PNG", "SVG"]) {
    const downloadPromise = page.waitForEvent("download");
    await page
      .getByRole("button", {
        name: `Export Average growth by treatment as ${type}`,
        exact: true,
      })
      .click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(
      new RegExp(`\\.${type.toLowerCase()}$`),
    );
  }
  await page
    .getByRole("button", { name: "Data Explorer", exact: true })
    .click();
  await expect(page.locator(".table-card tbody tr")).toHaveCount(25);
  await page.getByRole("button", { name: "Sort by plant_height_cm" }).click();
  await page.getByLabel("Search records").fill("Nutrient A");
  await expect(page.locator(".pagination")).toContainText("60 records");
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.locator(".pagination")).toContainText("Page 2");
  await page.getByRole("button", { name: "Overview", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Create chart", exact: true }),
  ).toBeEnabled();
  expect(errors).toEqual([]);
});

test("synthetic sample loading and responsive navigation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByText("Backend connected")).toBeVisible();
  await page.getByRole("button", { name: /Environmental monitoring/ }).click();
  await expect(
    page.getByRole("heading", { name: "environment synthetic", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".chart-card")).toHaveCount(4);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("button", { name: "Data Explorer", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Data Explorer", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Ask AI", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Ask DataLens AI" }),
  ).toBeVisible();
  await expect(page.getByLabel("Ask about your data")).toBeVisible();
  await page.getByRole("button", { name: "Close assistant" }).click();
  await expect(
    page.getByRole("heading", { name: "Ask DataLens AI" }),
  ).not.toBeVisible();
});
