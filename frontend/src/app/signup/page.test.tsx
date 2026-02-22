import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// mock next/navigation
const pushMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/signup",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

// mock auth context
const signupMock = vi.fn();
vi.mock("@/lib/auth-context", () => ({
  useAuth: () => ({
    user: null,
    isLoading: false,
    isAuthenticated: false,
    login: vi.fn(),
    signup: signupMock,
    logout: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import SignupPage from "@/app/signup/page";

describe("Signup page", () => {
  beforeEach(() => {
    pushMock.mockClear();
    signupMock.mockClear();
    signupMock.mockResolvedValue(undefined);
  });

  it("renders without crashing", () => {
    render(<SignupPage />);
  });

  it("shows role selection step initially", () => {
    render(<SignupPage />);
    expect(screen.getByText("Create your account")).toBeInTheDocument();
    expect(screen.getByText("Choose how you'll use CalmAI")).toBeInTheDocument();
  });

  it("displays Therapist and Patient role cards", () => {
    render(<SignupPage />);
    expect(screen.getByText("Therapist")).toBeInTheDocument();
    expect(screen.getByText("Patient")).toBeInTheDocument();
  });

  it("defaults to therapist role with correct continue button", () => {
    render(<SignupPage />);
    expect(screen.getByText(/Continue as Therapist/)).toBeInTheDocument();
  });

  it("switches to Patient role when Patient card is clicked", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText("Patient"));
    expect(screen.getByText(/Continue as Patient/)).toBeInTheDocument();
  });

  it("switches back to Therapist role when Therapist card is clicked", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText("Patient"));
    expect(screen.getByText(/Continue as Patient/)).toBeInTheDocument();

    await user.click(screen.getByText("Therapist"));
    expect(screen.getByText(/Continue as Therapist/)).toBeInTheDocument();
  });

  it("navigates to form step when Continue is clicked", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText(/Continue as Therapist/));

    expect(screen.getByText("Therapist Registration")).toBeInTheDocument();
    expect(screen.getByLabelText("First name")).toBeInTheDocument();
    expect(screen.getByLabelText("Last name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  it("shows therapist-specific fields in therapist form", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText(/Continue as Therapist/));

    expect(screen.getByLabelText("License number")).toBeInTheDocument();
    expect(screen.getByLabelText("Specialization")).toBeInTheDocument();
    expect(screen.getByLabelText(/Practice name/)).toBeInTheDocument();
  });

  it("shows patient-specific fields in patient form", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText("Patient"));
    await user.click(screen.getByText(/Continue as Patient/));

    expect(screen.getByText("Patient Registration")).toBeInTheDocument();
    expect(screen.getByLabelText("Therapist invite code")).toBeInTheDocument();
    expect(screen.getByLabelText("Date of birth")).toBeInTheDocument();
  });

  it("can go back from form to role selection", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText(/Continue as Therapist/));
    expect(screen.getByText("Therapist Registration")).toBeInTheDocument();

    await user.click(screen.getByText(/Back/));
    expect(screen.getByText("Create your account")).toBeInTheDocument();
  });

  it("has a link to the login page", () => {
    render(<SignupPage />);
    expect(screen.getByText("Log in")).toBeInTheDocument();
  });

  it("has a Create account button in the form step", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText(/Continue as Therapist/));
    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
  });

  it("shows loading state on form submission", async () => {
    signupMock.mockReturnValue(new Promise(() => {})); // never resolves
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText(/Continue as Therapist/));

    await user.type(screen.getByLabelText("First name"), "Jane");
    await user.type(screen.getByLabelText("Last name"), "Doe");
    await user.type(screen.getByLabelText("Email"), "jane@test.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("License number"), "PSY-1234");
    await user.type(screen.getByLabelText("Specialization"), "CBT");

    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(screen.getByText("Creating account...")).toBeInTheDocument();
  });

  it("calls signup with therapist payload", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText(/Continue as Therapist/));

    await user.type(screen.getByLabelText("First name"), "Jane");
    await user.type(screen.getByLabelText("Last name"), "Doe");
    await user.type(screen.getByLabelText("Email"), "jane@test.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("License number"), "PSY-1234");
    await user.type(screen.getByLabelText("Specialization"), "CBT");

    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(signupMock).toHaveBeenCalledWith(
        expect.objectContaining({
          email: "jane@test.com",
          password: "password123",
          name: "Jane Doe",
          role: "therapist",
          licenseNumber: "PSY-1234",
          specialization: "CBT",
        })
      );
    });
  });

  it("calls signup with patient payload", async () => {
    const user = userEvent.setup();
    render(<SignupPage />);

    await user.click(screen.getByText("Patient"));
    await user.click(screen.getByText(/Continue as Patient/));

    await user.type(screen.getByLabelText("First name"), "Alex");
    await user.type(screen.getByLabelText("Last name"), "Smith");
    await user.type(screen.getByLabelText("Email"), "alex@test.com");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.type(screen.getByLabelText("Therapist invite code"), "ABC123");
    await user.type(screen.getByLabelText("Date of birth"), "1995-01-01");

    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => {
      expect(signupMock).toHaveBeenCalledWith(
        expect.objectContaining({
          email: "alex@test.com",
          password: "password123",
          name: "Alex Smith",
          role: "patient",
          therapistId: "ABC123",
          dateOfBirth: "1995-01-01",
        })
      );
    });
  });
});
