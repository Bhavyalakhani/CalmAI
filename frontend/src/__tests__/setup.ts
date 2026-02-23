import "@testing-library/jest-dom/vitest";

// polyfill ResizeObserver for recharts in jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
