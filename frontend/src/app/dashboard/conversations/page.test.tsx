import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn(), refresh: vi.fn(), forward: vi.fn() }),
  usePathname: () => "/dashboard/conversations",
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

import { mockTherapist, mockConversations } from "@/__tests__/mock-api-data";

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
  fetchConversations: vi.fn(),
}));

import { fetchConversations } from "@/lib/api";
import ConversationsPage from "@/app/dashboard/conversations/page";

describe("Conversations page", () => {
  beforeEach(() => {
    vi.mocked(fetchConversations).mockResolvedValue({
      conversations: mockConversations,
      total: mockConversations.length,
      page: 1,
      pageSize: 20,
    });
  });

  it("renders without crashing", () => {
    render(<ConversationsPage />);
  });

  it("displays the conversations heading", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(screen.getByText("Conversation Explorer")).toBeInTheDocument();
    });
  });

  it("shows tab filters", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(screen.getByText("All Topics")).toBeInTheDocument();
      expect(screen.getByText("Anxiety")).toBeInTheDocument();
      expect(screen.getByText("Depression")).toBeInTheDocument();
    });
  });

  it("displays sample conversation content", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/panic attacks almost every day/)
      ).toBeInTheDocument();
    });
  });

  it("shows topic and severity badges", async () => {
    render(<ConversationsPage />);
    await waitFor(() => {
      expect(screen.getAllByText("anxiety").length).toBeGreaterThan(0);
      expect(screen.getAllByText("severe").length).toBeGreaterThan(0);
    });
  });
});
