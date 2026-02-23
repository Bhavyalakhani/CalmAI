import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { mockTherapist } from "@/__tests__/mock-api-data";

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

const mockLogout = vi.fn();

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: mockTherapist,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    signup: vi.fn(),
    logout: mockLogout,
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api", () => ({
  updateProfile: vi.fn(),
  updateNotifications: vi.fn(),
  deleteAccount: vi.fn(),
  logout: vi.fn(),
}));

import { updateProfile, updateNotifications, deleteAccount } from "@/lib/api";
import SettingsPage from "@/app/dashboard/settings/page";

describe("Dashboard settings page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(updateProfile).mockResolvedValue(mockTherapist);
    vi.mocked(updateNotifications).mockResolvedValue({ message: "saved" });
    vi.mocked(deleteAccount).mockResolvedValue(undefined);
  });

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

  it("populates default values from therapist user", () => {
    render(<SettingsPage />);
    expect(screen.getByDisplayValue("Dr. Sarah Chen")).toBeInTheDocument();
  });

  it("renders notification settings", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Notification Preferences")).toBeInTheDocument();
    expect(screen.getByText("Pipeline run status")).toBeInTheDocument();
  });

  it("renders delete confirmation input", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Danger Zone")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("DELETE")).toBeInTheDocument();
  });

  it("calls updateProfile API on save", async () => {
    render(<SettingsPage />);
    const saveBtn = screen.getByText("Save changes");
    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(updateProfile).toHaveBeenCalled();
    });
  });

  it("calls updateNotifications API on save", async () => {
    render(<SettingsPage />);
    const saveBtn = screen.getByText("Save notification preferences");
    fireEvent.click(saveBtn);
    await waitFor(() => {
      expect(updateNotifications).toHaveBeenCalled();
    });
  });

  it("calls deleteAccount API when DELETE is typed and confirmed", async () => {
    render(<SettingsPage />);
    const input = screen.getByPlaceholderText("DELETE");
    fireEvent.change(input, { target: { value: "DELETE" } });
    const deleteBtn = screen.getByText("Delete");
    fireEvent.click(deleteBtn);
    await waitFor(() => {
      expect(deleteAccount).toHaveBeenCalled();
    });
  });

  it("shows success message after profile save", async () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => {
      expect(screen.getByText("profile changes saved successfully.")).toBeInTheDocument();
    });
  });

  it("shows error message on profile save failure", async () => {
    vi.mocked(updateProfile).mockRejectedValue({ detail: "server error" });
    render(<SettingsPage />);
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => {
      expect(screen.getByText("server error")).toBeInTheDocument();
    });
  });

  it("shows success message after notification save", async () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getByText("Save notification preferences"));
    await waitFor(() => {
      expect(screen.getByText("notification preferences updated.")).toBeInTheDocument();
    });
  });

  it("shows error message on notification save failure", async () => {
    vi.mocked(updateNotifications).mockRejectedValue({ detail: "notif error" });
    render(<SettingsPage />);
    fireEvent.click(screen.getByText("Save notification preferences"));
    await waitFor(() => {
      expect(screen.getByText("notif error")).toBeInTheDocument();
    });
  });

  it("prevents save when name is empty", async () => {
    render(<SettingsPage />);
    const nameInput = screen.getByDisplayValue("Dr. Sarah Chen");
    fireEvent.change(nameInput, { target: { value: "" } });
    fireEvent.change(nameInput, { target: { value: "  " } });
    fireEvent.click(screen.getByText("Save changes"));
    await waitFor(() => {
      expect(screen.getByText("name is required.")).toBeInTheDocument();
    });
    // should not have called the API
    expect(vi.mocked(updateProfile)).not.toHaveBeenCalled();
  });

  it("disables delete button when DELETE is not typed", () => {
    render(<SettingsPage />);
    const deleteBtn = screen.getByText("Delete");
    expect(deleteBtn).toBeDisabled();
  });

  it("calls logout after successful account deletion", async () => {
    render(<SettingsPage />);
    const input = screen.getByPlaceholderText("DELETE");
    fireEvent.change(input, { target: { value: "DELETE" } });
    fireEvent.click(screen.getByText("Delete"));
    await waitFor(() => {
      expect(deleteAccount).toHaveBeenCalled();
    });
    // logout is called after a 350ms setTimeout
    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
    }, { timeout: 2000 });
  });

  it("shows pipeline status section", () => {
    render(<SettingsPage />);
    expect(screen.getByText("Pipeline Status")).toBeInTheDocument();
    expect(screen.getByText("Embedding Model")).toBeInTheDocument();
    expect(screen.getByText("Vector Store")).toBeInTheDocument();
    expect(screen.getByText("Incoming Journals Pipeline")).toBeInTheDocument();
  });

  it("has email and license fields disabled", () => {
    render(<SettingsPage />);
    const emailInput = screen.getByLabelText("Email");
    const licenseInput = screen.getByLabelText("License number");
    expect(emailInput).toBeDisabled();
    expect(licenseInput).toBeDisabled();
  });
});
