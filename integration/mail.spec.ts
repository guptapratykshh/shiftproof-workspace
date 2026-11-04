import { expect, test } from "@playwright/test";

for (const delivery of ["local_outbox", "smtp_queued"] as const) {
  test(`signup and recovery explain ${delivery} without claiming inbox delivery`, async ({ page }) => {
    // Test the delivery states without sending mail to an external inbox.
    await page.route("**/api/v1/auth/register", (route) => route.fulfill({
      status: 202,
      json: { status: "verification_required", delivery },
    }));
    await page.route("**/api/v1/auth/recover", (route) => route.fulfill({
      status: 202,
      json: { status: "recovery_requested", delivery },
    }));
    await page.setViewportSize({ width: 320, height: 900 });
    await page.goto("/signup");
    await page.getByLabel("Full name", { exact: true }).fill("Mail Test");
    await page.getByLabel("Organization name", { exact: true }).fill("Mail Test Organization");
    await page.getByLabel("Official organization email").fill("mail-test@example.com");
    await page.getByLabel("Organization type", { exact: true }).selectOption("manufacturing");
    await page.getByLabel("Password", { exact: true }).fill("Mail-testing-58371");
    await page.getByLabel("Confirm password", { exact: true }).fill("Mail-testing-58371");
    await page.getByRole("button", { name: "Create account", exact: true }).click();
    const status = page.locator(".success-card");
    await expect(status).toContainText(delivery === "local_outbox"
      ? "No email will arrive in your inbox."
      : "Your verification email is queued for delivery.");
    await expect(status).not.toContainText("We’ve sent");
    await page.getByRole("button", { name: "Switch to Hindi" }).click();
    await expect(status).toContainText(delivery === "local_outbox"
      ? "इनबॉक्स में ईमेल नहीं आएगा"
      : "ईमेल भेजने की कतार में है");
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(320);
    await page.getByRole("button", { name: "Switch to English" }).click();
    await page.goto("/recover/organization");
    await page.getByLabel("Email address", { exact: true }).fill("mail-test@example.com");
    await page.getByRole("button", { name: "Send reset link", exact: true }).click();
    await expect(status).toContainText(delivery === "local_outbox"
      ? "No email will arrive in your inbox."
      : "a password reset email will be queued for delivery");
  });
}
