import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { renderWithProviders } from "test-utils";
import type { InfraServer } from "#/api/infra/client";

vi.mock("@xterm/xterm/css/xterm.css", () => ({}));

vi.mock("#/api/local-auth/client", async () => {
  const actual = await vi.importActual<typeof import("#/api/local-auth/client")>(
    "#/api/local-auth/client",
  );
  return {
    ...actual,
    isLocalAuthEnabled: () => true,
  };
});

vi.mock("#/api/local-auth/hooks", () => ({
  useLocalAuthUser: () => ({
    data: {
      id: "u1",
      username: "admin",
      email: null,
      is_admin: true,
      credit_balance: 0,
    },
    isLoading: false,
  }),
}));

vi.mock("#/hooks/use-ssh-terminal", () => ({
  useSshTerminal: () => ({
    containerRef: { current: null },
    status: "closed",
    error: null,
    banner: null,
    reconnect: vi.fn(),
    disconnect: vi.fn(),
  }),
}));

const fetchInfraServers = vi.fn();
const updateInfraServer = vi.fn();
const setInfraCredentials = vi.fn();

vi.mock("#/api/infra/client", () => ({
  fetchInfraServers: (...args: unknown[]) => fetchInfraServers(...args),
  createInfraServer: vi.fn(),
  deleteInfraServer: vi.fn(),
  setInfraCredentials: (...args: unknown[]) => setInfraCredentials(...args),
  updateInfraServer: (...args: unknown[]) => updateInfraServer(...args),
}));

import HostSettingsScreen from "#/routes/host-settings";

const HOST: InfraServer = {
  id: "srv-1",
  name: "lab-box",
  hostname: "192.168.1.50",
  port: 22,
  username: "root",
  auth_type: "password",
  description: null,
  tags: [],
  is_active: true,
  last_seen_at: null,
  last_error: null,
};

describe("Host settings SSH password field", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    fetchInfraServers.mockReset();
    updateInfraServer.mockReset();
    setInfraCredentials.mockReset();
    fetchInfraServers.mockResolvedValue([HOST]);
    updateInfraServer.mockImplementation(async (_id, body) => ({
      ...HOST,
      ...body,
    }));
    setInfraCredentials.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  async function openHostDetails(user: ReturnType<typeof userEvent.setup>) {
    await user.click(await screen.findByRole("button", { name: /lab-box/i }));
    await user.click(screen.getByTestId("host-card-edit-srv-1"));
  }

  it("does not auto-save credentials while typing password", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(
      <MemoryRouter>
        <HostSettingsScreen />
      </MemoryRouter>,
    );

    await openHostDetails(user);
    const passwordInput = document.getElementById(
      "host-password",
    ) as HTMLInputElement;
    expect(passwordInput).toHaveAttribute("autocomplete", "off");
    expect(passwordInput).toHaveAttribute("type", "text");
    expect(passwordInput).toHaveAttribute("data-bwignore", "true");

    await user.type(passwordInput, "secret-pass");
    expect(passwordInput).toHaveValue("secret-pass");

    await vi.advanceTimersByTimeAsync(800);

    await waitFor(() => {
      expect(updateInfraServer).not.toHaveBeenCalled();
      expect(setInfraCredentials).not.toHaveBeenCalled();
    });
    expect(passwordInput).toHaveValue("secret-pass");
  });

  it("saves credentials only when Connect is clicked", async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(
      <MemoryRouter>
        <HostSettingsScreen />
      </MemoryRouter>,
    );

    await openHostDetails(user);
    const passwordInput = document.getElementById(
      "host-password",
    ) as HTMLInputElement;
    await user.type(passwordInput, "secret-pass");
    await user.click(screen.getByRole("button", { name: "Connect" }));

    await waitFor(() => {
      expect(setInfraCredentials).toHaveBeenCalledWith("srv-1", {
        credential: "secret-pass",
        auth_type: "password",
      });
    });
  });
});
