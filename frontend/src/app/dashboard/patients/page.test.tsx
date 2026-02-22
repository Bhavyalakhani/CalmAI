import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard/patients",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { mockTherapist, mockPatients, mockAnalytics } from "@/__tests__/mock-api-data";

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: mockTherapist,
    isLoading: false,
    isAuthenticated: true,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/lib/api", () => ({
  fetchPatients: vi.fn(),
  fetchAnalytics: vi.fn(),
  generateInviteCode: vi.fn(),
  fetchInviteCodes: vi.fn(),
}));

import { fetchPatients, fetchAnalytics, generateInviteCode, fetchInviteCodes } from "@/lib/api";
import PatientsPage from "@/app/dashboard/patients/page";

describe("Patients page", () => {
  beforeEach(() => {
    vi.mocked(fetchPatients).mockResolvedValue(mockPatients);
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
  });

  it("renders without crashing", () => {
    render(<PatientsPage />);
  });

  it("displays the Patient Management header", async () => {
    render(<PatientsPage />);
    await waitFor(() => {
      expect(screen.getByText("Patient Management")).toBeInTheDocument();
    });
  });

  it("displays the patient count", async () => {
    render(<PatientsPage />);
    await waitFor(() => {
      expect(screen.getByText("5 patients in your practice")).toBeInTheDocument();
    });
  });

  it("has a search input", async () => {
    render(<PatientsPage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search patients...")).toBeInTheDocument();
    });
  });

  it("has an Add Patient button", async () => {
    render(<PatientsPage />);
    await waitFor(() => {
      expect(screen.getByText("Add Patient")).toBeInTheDocument();
    });
  });

  it("renders patient cards for all patients", async () => {
    render(<PatientsPage />);
    await waitFor(() => {
      expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
      expect(screen.getByText("Jordan Kim")).toBeInTheDocument();
      expect(screen.getByText("Morgan Patel")).toBeInTheDocument();
      expect(screen.getByText("Casey Thompson")).toBeInTheDocument();
      expect(screen.getByText("Taylor Nguyen")).toBeInTheDocument();
    });
  });

  it("shows patient emails", async () => {
    render(<PatientsPage />);
    await waitFor(() => {
      expect(screen.getByText("alex.rivera@email.com")).toBeInTheDocument();
      expect(screen.getByText("jordan.kim@email.com")).toBeInTheDocument();
    });
  });

  it("opens invite dialog when Add Patient is clicked", async () => {
    vi.mocked(fetchInviteCodes).mockResolvedValue([]);
    const user = userEvent.setup();
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText("Add Patient")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Add Patient"));
    expect(screen.getByText("Invite a Patient")).toBeInTheDocument();
    expect(screen.getByText("Generate Invite Code")).toBeInTheDocument();
  });

  it("generates and displays an invite code", async () => {
    vi.mocked(fetchInviteCodes).mockResolvedValue([]);
    vi.mocked(generateInviteCode).mockResolvedValue({
      code: "ABCD1234",
      expiresAt: "2026-03-01T00:00:00Z",
      message: "Share this code with your patient",
    });

    const user = userEvent.setup();
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText("Add Patient")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Add Patient"));
    await user.click(screen.getByText("Generate Invite Code"));

    await waitFor(() => {
      expect(screen.getByText("ABCD1234")).toBeInTheDocument();
    });
  });

  it("shows previous codes in the dialog", async () => {
    vi.mocked(fetchInviteCodes).mockResolvedValue([
      {
        code: "PREV0001",
        therapistId: "t-001",
        therapistName: "Dr. Sarah Chen",
        createdAt: "2026-02-01T00:00:00Z",
        expiresAt: "2026-02-08T00:00:00Z",
        isUsed: true,
        usedBy: "p-999",
      },
    ]);

    const user = userEvent.setup();
    render(<PatientsPage />);

    await waitFor(() => {
      expect(screen.getByText("Add Patient")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Add Patient"));

    await waitFor(() => {
      expect(screen.getByText("PREV0001")).toBeInTheDocument();
      expect(screen.getByText("Used")).toBeInTheDocument();
    });
  });
});
