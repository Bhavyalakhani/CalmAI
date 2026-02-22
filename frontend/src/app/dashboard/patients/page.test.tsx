import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";

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

import PatientsPage from "@/app/dashboard/patients/page";

describe("Patients page", () => {
  it("renders without crashing", () => {
    render(<PatientsPage />);
  });

  it("displays the Patient Management header", () => {
    render(<PatientsPage />);
    expect(screen.getByText("Patient Management")).toBeInTheDocument();
  });

  it("displays the patient count", () => {
    render(<PatientsPage />);
    expect(screen.getByText("5 patients in your practice")).toBeInTheDocument();
  });

  it("has a search input", () => {
    render(<PatientsPage />);
    expect(screen.getByPlaceholderText("Search patients...")).toBeInTheDocument();
  });

  it("has an Add Patient button", () => {
    render(<PatientsPage />);
    expect(screen.getByText("Add Patient")).toBeInTheDocument();
  });

  it("renders patient cards for all patients", () => {
    render(<PatientsPage />);
    expect(screen.getByText("Alex Rivera")).toBeInTheDocument();
    expect(screen.getByText("Jordan Kim")).toBeInTheDocument();
    expect(screen.getByText("Morgan Patel")).toBeInTheDocument();
    expect(screen.getByText("Casey Thompson")).toBeInTheDocument();
    expect(screen.getByText("Taylor Nguyen")).toBeInTheDocument();
  });

  it("shows patient emails", () => {
    render(<PatientsPage />);
    expect(screen.getByText("alex.rivera@email.com")).toBeInTheDocument();
    expect(screen.getByText("jordan.kim@email.com")).toBeInTheDocument();
  });
});
