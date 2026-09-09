import { describe, expect, it } from "vitest";
import { prepareMockBrowserDefaults } from "#/mocks/handlers";

describe("mock SaaS admin handlers", () => {
  it("reports onboarding as complete so the guard does not redirect", async () => {
    const res = await fetch("/api/onboarding_status");
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual({
      should_complete_onboarding: false,
    });
  });

  it("returns a V1 conversation page for the sidebar/home search", async () => {
    const res = await fetch("/api/v1/app-conversations/search?limit=10");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.items)).toBe(true);
    expect(body.items.length).toBeGreaterThan(0);
    expect(body.next_page_id).toBeNull();
    expect(body.items[0]).toEqual(
      expect.objectContaining({
        id: expect.any(String),
        title: expect.any(String),
        sandbox_id: expect.any(String),
      }),
    );
  });

  it("serves default settings after browser mock seeding", async () => {
    prepareMockBrowserDefaults();
    const res = await fetch("/api/v1/settings");
    expect(res.status).toBe(200);
    const settings = await res.json();
    expect(settings).toEqual(
      expect.objectContaining({ llm_model: expect.any(String) }),
    );
  });

  it("returns the current user's git organizations", async () => {
    const res = await fetch("/api/v1/users/git-organizations");
    expect(res.status).toBe(200);
    await expect(res.json()).resolves.toEqual({
      provider: "github",
      organizations: ["mock-git-org"],
    });
  });

  it("returns git claims, LLM profiles, and org settings for an org", async () => {
    const claims = await fetch("/api/organizations/1/git-claims");
    expect(claims.status).toBe(200);
    await expect(claims.json()).resolves.toEqual([]);

    const profiles = await fetch("/api/organizations/1/profiles");
    expect(profiles.status).toBe(200);
    const profileBody = await profiles.json();
    expect(profileBody).toEqual(
      expect.objectContaining({
        profiles: expect.any(Array),
        active_profile: expect.anything(),
      }),
    );

    prepareMockBrowserDefaults();
    const settings = await fetch("/api/organizations/1/settings");
    expect(settings.status).toBe(200);
    const settingsBody = await settings.json();
    expect(settingsBody).toEqual(
      expect.objectContaining({
        agent_settings: expect.any(Object),
        llm_api_key_set: expect.any(Boolean),
      }),
    );
  });

  it("returns usage dashboard stats instead of falling through to a 404", async () => {
    const stats = await fetch("/api/organizations/1/conversations/stats");
    expect(stats.status).toBe(200);
    await expect(stats.json()).resolves.toEqual(
      expect.objectContaining({
        active_conversations: expect.any(Number),
        total_cost: expect.any(Number),
      }),
    );

    const usage = await fetch(
      "/api/organizations/1/conversations/usage-stats?days=7",
    );
    expect(usage.status).toBe(200);
    await expect(usage.json()).resolves.toEqual(
      expect.objectContaining({
        daily_usage: expect.any(Array),
        team_usage: expect.any(Array),
      }),
    );

    const userUsage = await fetch(
      "/api/organizations/1/conversations/user-usage",
    );
    expect(userUsage.status).toBe(200);
    await expect(userUsage.json()).resolves.toEqual(
      expect.objectContaining({ items: expect.any(Array) }),
    );

    const budgets = await fetch(
      "/api/organizations/1/budgets?users_page=1&users_per_page=50",
    );
    expect(budgets.status).toBe(200);
    await expect(budgets.json()).resolves.toEqual(
      expect.objectContaining({
        enabled: expect.any(Boolean),
        users: expect.any(Array),
      }),
    );
  });

  it("does not point PostHog at a fake CDN key in mock mode", async () => {
    const res = await fetch("/api/v1/web-client/config");
    expect(res.status).toBe(200);
    const config = await res.json();
    expect(config.posthog_client_key).toBeNull();
  });
});
