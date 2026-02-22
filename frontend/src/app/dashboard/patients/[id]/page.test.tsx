import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard/patients/p-001",
  useSearchParams: () => new URLSearchParams(),
  useParams: () => ({ id: "p-001" }),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { mockTherapist, mockPatient, mockAnalytics, mockJournals } from "@/__tests__/mock-api-data";

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
  fetchPatient: vi.fn(),
  fetchAnalytics: vi.fn(),
  fetchJournals: vi.fn(),
  fetchMoodTrend: vi.fn(),
}));

import { fetchPatient, fetchAnalytics, fetchJournals, fetchMoodTrend } from "@/lib/api";
import PatientProfilePage from "@/app/dashboard/patients/[id]/page";

describe("Patient profile page", () => {
  beforeEach(() => {
    vi.mocked(fetchPatient).mockResolvedValue(mockPatient);
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
    vi.mocked(fetchJournals).mockResolvedValue(mockJournals);
    vi.mocked(fetchMoodTrend).mockResolvedValue([]);
  });

  it("renders without crashing", () => {
    render(<PatientProfilePage />);
  });

  it("displays the patient name", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
    });
  });

  it("displays the patient email", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getAllByText("alex.rivera@email.com").length).toBeGreaterThan(0);
    });
  });

  it("displays journal entries", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Journal Entries")).toBeInTheDocument();
    });
  });

  it("displays theme distribution", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Theme Distribution")).toBeInTheDocument();
    });
  });

  it("displays summary stats", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Summary")).toBeInTheDocument();
    });
  });

  it("displays journal content", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(
        screen.getByText(/breathing exercises really helped/)
      ).toBeInTheDocument();
    });
  });

  it("shows filter controls", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search journal content...")).toBeInTheDocument();
    });
  });

  it("shows patient not found for invalid id", async () => {
    vi.mocked(fetchPatient).mockRejectedValue(new Error("not found"));
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Patient not found")).toBeInTheDocument();
    });
  });
});
