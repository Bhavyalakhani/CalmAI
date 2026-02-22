import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard/settings",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import SettingsPage from "@/app/dashboard/settings/page";

describe("Dashboard settings page", () => {
  it("renders without crashing", () => {
    render(<SettingsPage />);
  });

  it("displays the settings heading", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("shows the profile section", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Your therapist profile information")).toBeInTheDocument();
  });

  it("populates default values from mock therapist", () => {
    render(<SettingsPage />);
    expect(screen.getByDisplayValue("Dr. Sarah Chen")).toBeInTheDocument();
  });
});
