import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getProxyBaseUrl, setGlobalLitellmHeaderName } from "@/components/networking";
import SkillDetail from "./skill_detail";
import type { Plugin } from "./types";

const digest = "a".repeat(64);
const archivePath = `/claude-code/plugins/my-skill/archive/${digest}.zip`;
const archiveUrl = () => `${getProxyBaseUrl()}${archivePath}`;
const createObjectURL = vi.fn((_blob: Blob) => "blob:skill-download");
const archiveResponse = vi.fn<() => Promise<Response>>();
const fetchMock = vi.fn<typeof fetch>();
let queryClient: QueryClient;

const buildSkill = (url = archiveUrl()): Plugin => ({
  id: "plugin-id",
  name: "my-skill",
  source: { source: "archive", url, sha256: digest },
  enabled: true,
  visibility: "private",
  version: null,
  description: null,
  created_at: null,
  updated_at: null,
});

const renderSkill = (skill = buildSkill()) =>
  render(
    <QueryClientProvider client={queryClient}>
      <SkillDetail skill={skill} onBack={vi.fn()} accessToken="dashboard-token" />
    </QueryClientProvider>,
  );

beforeEach(() => {
  vi.clearAllMocks();
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
  Object.defineProperty(URL, "createObjectURL", { configurable: true, writable: true, value: createObjectURL });
  setGlobalLitellmHeaderName("X-LiteLLM-Key");
  archiveResponse.mockResolvedValue(new Response("zip-bytes", { headers: { "Content-Type": "application/zip" } }));
  fetchMock.mockImplementation(async (input) => {
    const url = input instanceof Request ? input.url : String(input);
    if (url.endsWith("/.well-known/litellm-ui-config")) {
      return Response.json({ claude_code_marketplace_auth_required: true });
    }
    if (url === archiveUrl()) return archiveResponse();
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  queryClient.clear();
  setGlobalLitellmHeaderName();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("SkillDetail uploaded archive download", () => {
  it("downloads the private archive through the shared client using the configured auth header", async () => {
    const downloadClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      expect(this.download).toBe("my-skill.zip");
      expect(this.href).toBe("blob:skill-download");
    });
    const revokeObjectURL = vi.spyOn(URL, "revokeObjectURL");
    renderSkill();
    fireEvent.click(screen.getByRole("button", { name: "Download ZIP" }));
    expect(screen.getByRole("button", { name: "Downloading…" })).toBeDisabled();

    await waitFor(() => expect(downloadClick).toHaveBeenCalledOnce());
    expect(fetchMock).toHaveBeenCalledWith(
      archiveUrl(),
      expect.objectContaining({
        method: "GET",
        headers: expect.objectContaining({ "X-LiteLLM-Key": "Bearer dashboard-token" }),
        redirect: "error",
      }),
    );
    const downloadedText = await new Promise<string>((resolve) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.readAsText(createObjectURL.mock.calls[0][0]);
    });
    expect(downloadedText).toBe("zip-bytes");
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:skill-download");
    expect(screen.getByRole("button", { name: "Download ZIP" })).toBeEnabled();
  });

  it("shows a failed request and allows retry without downloading an error response", async () => {
    archiveResponse.mockResolvedValueOnce(Response.json({ detail: "Skill archive not found" }, { status: 404 }));
    renderSkill();
    fireEvent.click(screen.getByRole("button", { name: "Download ZIP" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Skill archive not found");
    expect(createObjectURL).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Download ZIP" }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledOnce());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("keeps external archives as ordinary links even if they copy the gateway route", () => {
    const externalUrl = `https://external.example.com${archivePath}`;
    renderSkill(buildSkill(externalUrl));

    expect(screen.getByRole("link", { name: externalUrl.replace("https://", "") })).toHaveAttribute(
      "href",
      externalUrl,
    );
    expect(screen.getByRole("link")).toHaveAttribute("target", "_blank");
    expect(screen.queryByRole("button", { name: "Download ZIP" })).not.toBeInTheDocument();
    expect(archiveResponse).not.toHaveBeenCalled();
  });
});
