import { expect, test } from "@playwright/test";

test("landing industry controls stay in sync and support keyboard navigation", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "Work changes hands.",
  );
  await page
    .getByRole("combobox", { name: "Handover industry" })
    .selectOption("1");
  await expect(
    page.getByRole("tab", { name: "Equipment maintenance Working workflow" }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel")).toContainText(
    "Safety check pending",
  );
  await page.getByRole("tab", { name: "Warehousing Working workflow" }).click();
  await expect(page.getByRole("combobox")).toHaveValue("2");
  await expect(page.locator(".scenario-condition")).toContainText(
    "Stock count pending",
  );
  await page
    .getByRole("tab", { name: "Warehousing Working workflow" })
    .press("ArrowRight");
  await expect(
    page.getByRole("tab", { name: "Quality assurance Planned workflow" }),
  ).toBeFocused();
  await expect(page.getByRole("tabpanel")).toContainText(
    "Planned · future workflow",
  );
});

test("role choices lead to the documented role-specific fields", async ({
  page,
}) => {
  await page.goto("/signin");
  await expect(page.locator(".role-card")).toHaveCount(3);
  await page
    .getByRole("link", { name: "Continue: Sign in as a worker" })
    .click();
  await expect(
    page.getByLabel("Organization ID", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Employee ID", { exact: true })).toBeVisible();
  await expect(page.getByLabel("6-digit PIN", { exact: true })).toBeVisible();
  await expect(page.getByRole("textbox", { name: /email/i })).toHaveCount(0);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByText("Enter your 6-digit PIN.")).toBeVisible();
  await page.getByRole("link", { name: "All sign-in options" }).click();
  await page
    .getByRole("link", { name: "Continue: Sign in as a supervisor" })
    .click();
  await expect(
    page.getByLabel("Organization ID", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Email address", { exact: true })).toBeVisible();
  await page.goto("/signin/organization");
  await expect(page.getByLabel("Official organization email")).toBeVisible();
  await expect(page.getByLabel("Organization ID", { exact: true })).toHaveCount(
    0,
  );
});

test("theme icon switches directly, persists, and migrates older system preferences", async ({
  page,
}) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.getByRole("button", { name: "Switch to dark theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(page.locator(".theme-menu, #theme-options")).toHaveCount(0);
  await page.getByRole("link", { name: "Build your workspace" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.getByRole("button", { name: "Switch to light theme" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  for (const scheme of ["dark", "light"] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.evaluate(() =>
      localStorage.setItem("shiftproof-theme", "system"),
    );
    await page.reload();
    await expect(page.locator("html")).toHaveAttribute("data-theme", scheme);
    expect(
      await page.evaluate(() => localStorage.getItem("shiftproof-theme")),
    ).toBe(scheme);
    const opposite = scheme === "dark" ? "light" : "dark";
    await page
      .getByRole("button", { name: `Switch to ${opposite} theme` })
      .click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", opposite);
  }
});

test("signup validates fields and never fabricates account creation", async ({
  page,
}) => {
  await page.goto("/signup");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByText("Enter your full name.")).toBeVisible();
  await expect(page.getByText("Choose an organization type.")).toBeVisible();
  await page.getByLabel("Full name", { exact: true }).fill("Asha Sharma");
  await page
    .getByLabel("Organization name", { exact: true })
    .fill("Sample Manufacturing");
  await page.getByLabel("Official organization email").fill("asha@example.com");
  await page
    .getByLabel("Organization type", { exact: true })
    .selectOption("manufacturing");
  await expect(
    page.getByLabel("Organization type", { exact: true }).locator("option"),
  ).toHaveCount(9);
  await page.getByLabel("Password", { exact: true }).fill("example-test-123");
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("different-test-123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByText("Passwords don’t match.")).toBeVisible();
  await page
    .getByLabel("Confirm password", { exact: true })
    .fill("example-test-123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Your details have not been submitted.",
  );
  await expect(page.getByLabel("Full name", { exact: true })).toHaveValue(
    "Asha Sharma",
  );
  await expect(
    page.getByRole("heading", { name: "Check your email" }),
  ).toHaveCount(0);
  const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }));
  expect(stored).not.toContain("example-test-123");
  expect(stored).not.toContain("asha@example.com");
});

test("language changes across every route and persists", async ({ page }) => {
  await page.goto("/signin");
  await page.getByRole("button", { name: "Switch to Hindi" }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "hi");
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "आप कैसे साइन इन करना चाहेंगे?",
  );
  await page.getByRole("link", { name: "एक संगठन बनाएँ", exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText(
    "अपना संगठन बनाएँ",
  );
  await page.reload();
  await expect(page.getByLabel("पूरा नाम", { exact: true })).toBeVisible();
});

test("worker PIN recovery explains the authorized recovery path", async ({
  page,
}) => {
  await page.goto("/signin/worker");
  await page.getByRole("link", { name: "Forgot your PIN?" }).click();
  await expect(
    page.getByRole("heading", { name: "Contact your supervisor" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "You don’t need an email address to access your worker account.",
    ),
  ).toBeVisible();
});

for (const width of [320, 390, 768, 900, 1169, 1470, 1600, 1920, 2560]) {
  test(`all pages fit ${width}px in both themes and languages`, async ({
    page,
  }) => {
    test.setTimeout(60_000);
    await page.setViewportSize({ width, height: 1000 });
    const routes = [
      "/",
      "/signin",
      "/signup",
      "/signin/worker",
      "/signin/supervisor",
      "/signin/organization",
      "/recover/worker",
      "/recover/supervisor",
      "/recover/organization",
      "/activate",
      "/verify-email",
      "/page-not-found",
    ];
    for (const theme of ["dark", "light"]) {
      for (const language of ["en", "hi"]) {
        await page.goto("/");
        await page.evaluate(
          ({ theme, language }) => {
            localStorage.setItem("shiftproof-theme", theme);
            localStorage.setItem("shiftproof-language", language);
          },
          { theme, language },
        );
        for (const route of routes) {
          await page.goto(route);
          await page.evaluate(() => document.fonts.ready);
          const context = `${route}, ${theme}, ${language}, ${width}px`;
          await expect(page.locator("html")).toHaveAttribute(
            "data-theme",
            theme,
          );
          await expect(page.locator("html")).toHaveAttribute("lang", language);
          expect(
            await page.evaluate(() => document.documentElement.scrollWidth),
            context,
          ).toBeLessThanOrEqual(width);
          await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
          const gutter =
            width <= 600
              ? 16
              : width <= 1000
                ? 24
                : Math.min(48, Math.max(32, width * 0.025));
          const header = await page.locator(".site-header").boundingBox();
          expect(header!.x, context).toBeCloseTo(gutter, 1);
          expect(header!.width, context).toBeCloseTo(width - 2 * gutter, 1);
          if (route === "/") {
            const sections = await page.locator(".marketing-container").all();
            for (const section of sections) {
              const box = await section.boundingBox();
              expect(box!.x, context).toBeCloseTo(gutter, 1);
              expect(box!.width, context).toBeCloseTo(header!.width, 1);
            }
            if (width > 760) {
              const scene = await page.locator(".factory-scene").boundingBox();
              expect(scene!.height, context).toBeLessThanOrEqual(320);
            }
          }
          const clipped = await page
            .locator(
              "main h1, main h2, main h3, main button, main a.button, main input, main select",
            )
            .evaluateAll((elements) =>
              elements
                .filter((element) => {
                  const box = element.getBoundingClientRect();
                  if (!box.width) return false;
                  return (
                    box.left < -1 ||
                    box.right > innerWidth + 1 ||
                    (!(element instanceof HTMLInputElement) &&
                      !(element instanceof HTMLSelectElement) &&
                      element.scrollWidth > element.clientWidth + 1)
                  );
                })
                .map((element) => element.textContent?.trim() || element.id),
            );
          expect(clipped, context).toEqual([]);
        }
      }
    }
  });
}

test("keyboard focus, direct theme switching and password visibility work without a mouse", async ({
  page,
}) => {
  await page.goto("/signup");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Skip to content" }),
  ).toBeFocused();
  await page.getByRole("button", { name: "Switch to dark theme" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await expect(
    page.getByRole("button", { name: "Switch to light theme" }),
  ).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(
    page.getByRole("button", { name: "Switch to dark theme" }),
  ).toBeFocused();
  await page.getByLabel("Password", { exact: true }).fill("visible-test-123");
  await page.getByRole("button", { name: "Show secret" }).first().focus();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute(
    "type",
    "password",
  );
});

test("visual review captures and no client errors", async ({
  page,
  browser,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const desktop = await browser.newContext({
    baseURL: testInfo.project.use.baseURL,
    viewport: { width: 1470, height: 801 },
    deviceScaleFactor: 2,
  });
  const desktopPage = await desktop.newPage();
  desktopPage.on("pageerror", (error) => errors.push(error.message));
  await desktopPage.goto("/");
  await desktopPage.evaluate(() => document.fonts.ready);
  await desktopPage.screenshot({
    path: testInfo.outputPath("landing-desktop.png"),
    fullPage: true,
  });
  await desktopPage.screenshot({
    path: testInfo.outputPath("landing-desktop-viewport.png"),
  });
  await desktop.close();
  await page.setViewportSize({ width: 1600, height: 870 });
  await page.goto("/signin");
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: testInfo.outputPath("signin-desktop.png"),
    fullPage: true,
  });
  await page.goto("/signup");
  await page.screenshot({
    path: testInfo.outputPath("signup-desktop.png"),
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.screenshot({
    path: testInfo.outputPath("signup-errors-desktop.png"),
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page.screenshot({
    path: testInfo.outputPath("landing-mobile.png"),
    fullPage: true,
  });
  await page.goto("/signin");
  await page.screenshot({
    path: testInfo.outputPath("signin-mobile.png"),
    fullPage: true,
  });
  await page.goto("/signup");
  await page.screenshot({
    path: testInfo.outputPath("signup-mobile-light.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Switch to Hindi" }).click();
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: testInfo.outputPath("signup-mobile-hindi.png"),
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
