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

import { mockTherapist, mockPatient, mockAnalytics, mockJournals, mockPrompts } from "@/__tests__/mock-api-data";

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
  fetchAllPrompts: vi.fn(),
  createPrompt: vi.fn(),
  removePatient: vi.fn().mockResolvedValue(undefined),
}));

import { fetchPatient, fetchAnalytics, fetchJournals, fetchMoodTrend, fetchAllPrompts } from "@/lib/api";
import PatientProfilePage from "@/app/dashboard/patients/[id]/page";

describe("Patient profile page", () => {
  beforeEach(() => {
    vi.mocked(fetchPatient).mockResolvedValue(mockPatient);
    vi.mocked(fetchAnalytics).mockResolvedValue(mockAnalytics);
    vi.mocked(fetchJournals).mockResolvedValue(mockJournals);
    vi.mocked(fetchMoodTrend).mockResolvedValue([]);
    vi.mocked(fetchAllPrompts).mockResolvedValue(mockPrompts);
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
      expect(screen.getAllByText("Processed Entries").length).toBeGreaterThan(0);
    });
  });

  it("displays topic distribution", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Topic Distribution")).toBeInTheDocument();
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

  it("shows Assign Prompt button", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Assign Prompt")).toBeInTheDocument();
    });
  });

  it("shows assigned prompts section", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Assigned Prompts")).toBeInTheDocument();
    });
  });

  it("shows Remove button", async () => {
    render(<PatientProfilePage />);
    await waitFor(() => {
      expect(screen.getByText("Remove")).toBeInTheDocument();
    });
  });
});
