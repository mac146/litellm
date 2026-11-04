import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { DashboardHeader } from "./DashboardHeader";
import { CommandPaletteProvider } from "@/components/CommandPalette/CommandPaletteProvider";

const { state } = vi.hoisted(() => ({
  state: { pathname: "/ui/logs", hidePrompts: false, hideBlog: false, worker: null as string | null },
}));

vi.mock("next/navigation", () => ({ usePathname: () => state.pathname }));
vi.mock("@/hooks/useWorker", () => ({
  useWorker: () => ({ isControlPlane: state.worker !== null, selectedWorker: state.worker }),
}));
vi.mock("@/app/(dashboard)/hooks/useDisableShowPrompts", () => ({ useDisableShowPrompts: () => state.hidePrompts }));
vi.mock("@/app/(dashboard)/hooks/useDisableBlogPosts", () => ({ useDisableBlogPosts: () => state.hideBlog }));
vi.mock("@/app/(dashboard)/hooks/blogPosts/useBlogPosts", () => ({ useBlogPosts: () => ({ data: { posts: [] } }) }));
vi.mock("@/components/Navbar/NotificationsBell/NotificationsBell", () => ({
  NotificationsBell: ({ footer }: { footer?: React.ReactNode }) => <div data-testid="bell">{footer}</div>,
}));
vi.mock("@/components/Navbar/WorkerDropdown/WorkerDropdown", () => ({
  default: () => <div data-testid="worker-dropdown" />,
}));

const renderHeader = () =>
  render(
    <CommandPaletteProvider>
      <DashboardHeader accessToken={null} deploymentHealth={<span data-testid="health" />} />
    </CommandPaletteProvider>,
  );

describe("DashboardHeader", () => {
  afterEach(() => {
    state.pathname = "/ui/logs";
    state.hidePrompts = false;
    state.hideBlog = false;
    state.worker = null;
  });

  it("titles the bar from the current route", () => {
    state.pathname = "/ui/models-and-endpoints";
    renderHeader();

    expect(screen.getByRole("heading", { level: 1, name: "Models + Endpoints" })).toBeInTheDocument();
  });

  it("titles the Aria route with the agent name", () => {
    state.pathname = "/ui/aria";
    renderHeader();

    expect(screen.getByRole("heading", { level: 1, name: "Aria Agent" })).toBeInTheDocument();
  });

  it("shows search, community links, health and the bell with resources in its footer", () => {
    renderHeader();

    expect(screen.getAllByRole("button", { name: /search/i }).length).toBeGreaterThan(0);
    const community = screen.getByRole("navigation", { name: "Docs and community" });
    expect(within(community).getByRole("link", { name: "Discord" })).toHaveAttribute(
      "href",
      "https://discord.gg/wuPM9dRgDw",
    );
    expect(screen.getByTestId("health")).toBeInTheDocument();
    expect(screen.getByTestId("bell")).toContainElement(screen.getByRole("navigation", { name: "Help and resources" }));
    expect(screen.queryByTestId("worker-dropdown")).not.toBeInTheDocument();
  });

  it("drops the community icons when prompts are hidden but keeps Docs in the bell", () => {
    state.hidePrompts = true;
    renderHeader();

    expect(screen.queryByRole("link", { name: "GitHub" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /docs/i })).toHaveAttribute("href", "https://docs.litellm.ai/docs/");
  });

  it("shows the worker switcher in control plane mode", () => {
    state.worker = "worker-1";
    renderHeader();

    expect(screen.getByTestId("worker-dropdown")).toBeInTheDocument();
  });
});
