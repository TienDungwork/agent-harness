import React from "react";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
const deleteInfraServer = vi.fn();

vi.mock("#/api/infra/client", () => ({
  fetchInfraServers: (...args: unknown[]) => fetchInfraServers(...args),
  createInfraServer: vi.fn(),
  deleteInfraServer: (...args: unknown[]) => deleteInfraServer(...args),
  setInfraCredentials: vi.fn(),
  updateInfraServer: vi.fn(),
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

describe("Host details More menu", () => {
  beforeEach(() => {
    fetchInfraServers.mockReset();
    deleteInfraServer.mockReset();
    fetchInfraServers.mockResolvedValue([HOST]);
    deleteInfraServer.mockResolvedValue(undefined);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("opens Connect and Remove instead of a new page", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MemoryRouter>
        <HostSettingsScreen />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /lab-box/i }));
    await user.click(screen.getByTestId("host-details-more"));

    expect(screen.getByTestId("host-details-more-menu")).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Connect" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Remove" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "More" })).not.toBeInTheDocument();
  });

  it("Connect from More opens a terminal tab on this page", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <MemoryRouter>
        <HostSettingsScreen />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /lab-box/i }));
    await user.click(screen.getByTestId("host-details-more"));
    await user.click(screen.getByRole("menuitem", { name: "Connect" }));

    expect(await screen.findByRole("button", { name: "lab-box" })).toBeInTheDocument();
    expect(screen.getByText(/closed/i)).toBeInTheDocument();
  });

  it("Remove from More deletes the host", async () => {
    const user = userEvent.setup();
    deleteInfraServer.mockImplementation(async () => {
      fetchInfraServers.mockResolvedValue([]);
    });

    renderWithProviders(
      <MemoryRouter>
        <HostSettingsScreen />
      </MemoryRouter>,
    );

    await user.click(await screen.findByRole("button", { name: /lab-box/i }));
    expect(
      await screen.findByRole("heading", { name: "lab-box" }),
    ).toBeInTheDocument();
    await user.click(screen.getByTestId("host-details-more"));
    await user.click(screen.getByRole("menuitem", { name: "Remove" }));

    await waitFor(() => {
      expect(deleteInfraServer).toHaveBeenCalledWith("srv-1");
    });
  });
});
