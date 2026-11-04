"use client";

import { useTerminology } from "@/contexts/TerminologyContext";
import { ToolbarSeparator } from "@/components/shared/ToolbarSeparator";
import { getBreadcrumb } from "@/components/leftnav";
import { NotificationsBell } from "@/components/Navbar/NotificationsBell/NotificationsBell";
import WorkerDropdown from "@/components/Navbar/WorkerDropdown/WorkerDropdown";
import { BellResources, InlineResourceLinks } from "@/components/TopBar/ResourceLinks";
import { CommandPaletteTrigger } from "@/components/CommandPalette/CommandPaletteTrigger";
import { useWorker } from "@/hooks/useWorker";
import { clearTokenCookies } from "@/utils/cookieUtils";
import { clearStoredReturnUrl, getLoginUrl } from "@/utils/returnUrlUtils";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

// Top bar for the dashboard shell. Sits only over the content column: the brand,
// workspace switcher and Aria live in the sidebar. Breakpoints are container
// queries on the header itself, so the bar adapts when the sidebar collapses.
export function DashboardHeader({
  accessToken,
  navigationTrigger,
  deploymentHealth,
}: {
  accessToken: string | null;
  navigationTrigger?: ReactNode;
  deploymentHealth?: ReactNode;
}) {
  const term = useTerminology();
  const { title } = getBreadcrumb(usePathname());
  const { isControlPlane, selectedWorker } = useWorker();
  const showWorkerSwitch = isControlPlane && selectedWorker !== null;

  const handleWorkerSwitch = (workerId: string) => {
    clearTokenCookies();
    clearStoredReturnUrl();
    localStorage.removeItem("litellm_selected_worker_id");
    localStorage.removeItem("litellm_worker_url");
    window.location.href = `${getLoginUrl()}?worker=${encodeURIComponent(workerId)}`;
  };

  return (
    <header className="@container flex h-14 flex-none items-center gap-2 border-b border-border bg-background px-2 md:px-4">
      {navigationTrigger}
      <h1 className="min-w-0 flex-1 truncate text-[15px] font-semibold text-foreground">{term(title)}</h1>
      <CommandPaletteTrigger className="hidden w-56 @min-[560px]:flex @min-[900px]:w-72 @min-[1200px]:w-96" />
      <div className="flex flex-none items-center gap-1">
        <CommandPaletteTrigger mobile className="size-8 text-muted-foreground @min-[560px]:hidden" />
        {showWorkerSwitch && <WorkerDropdown onWorkerSwitch={handleWorkerSwitch} />}
        <InlineResourceLinks textLinks={false} className="hidden @min-[760px]:flex" />
        <ToolbarSeparator className="hidden @min-[760px]:block" />
        {deploymentHealth}
        <NotificationsBell accessToken={accessToken} footer={<BellResources />} />
      </div>
    </header>
  );
}

export default DashboardHeader;
