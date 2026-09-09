import { describe, expect, it } from "vitest";
import { i18nBackendLoadPath } from "#/i18n";

describe("i18nBackendLoadPath", () => {
  it("keeps root locales when the app is mounted at /", () => {
    expect(i18nBackendLoadPath("/")).toBe("/locales/{{lng}}/{{ns}}.json");
  });

  it("prefixes locales with the Vite base path used by the admin gateway", () => {
    expect(i18nBackendLoadPath("/admin/")).toBe(
      "/admin/locales/{{lng}}/{{ns}}.json",
    );
    expect(i18nBackendLoadPath("/admin")).toBe(
      "/admin/locales/{{lng}}/{{ns}}.json",
    );
  });
});
