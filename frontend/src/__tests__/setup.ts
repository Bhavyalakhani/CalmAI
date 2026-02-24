import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";

// polyfill ResizeObserver for recharts in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// global mock for theme context so all components using ThemeToggle render fine
vi.mock("@/lib/theme-context", () => ({
  useTheme: () => ({ theme: "dark", toggleTheme: vi.fn() }),
  ThemeProvider: ({ children }: { children: React.ReactNode }) => children,
}));
