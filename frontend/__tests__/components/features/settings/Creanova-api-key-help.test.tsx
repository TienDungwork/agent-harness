import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CreanovaApiKeyHelp } from "#/components/features/settings/Creanova-api-key-help";

describe("CreanovaApiKeyHelp", () => {
  it("renders the help link with the provided testId", () => {
    render(<CreanovaApiKeyHelp testId="oh-api-key-help" />);

    expect(screen.getByTestId("oh-api-key-help")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "SETTINGS$NAV_API_KEYS" }),
    ).toHaveAttribute("href", "https://app.all-hands.dev/settings/api-keys");
  });

  it("renders the billing info paragraph with the pricing-details link", () => {
    render(<CreanovaApiKeyHelp testId="oh-api-key-help" />);

    expect(screen.getByText("SETTINGS$LLM_BILLING_INFO")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "SETTINGS$SEE_PRICING_DETAILS" }),
    ).toHaveAttribute(
      "href",
      "https://docs.Creanova.dev/usage/llms/Creanova-llms",
    );
  });
});
