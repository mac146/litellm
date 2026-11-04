import { useHealthReadinessDetails } from "@/app/(dashboard)/hooks/healthReadiness/useHealthReadinessDetails";
import { useDisableBouncingIcon } from "@/app/(dashboard)/hooks/useDisableBouncingIcon";
import { useWorker } from "@/hooks/useWorker";
import { getProxyBaseUrl } from "@/components/networking";
import { uiHref } from "@/utils/uiHref";
import { useTheme } from "@/contexts/ThemeContext";
import { revokeSessionAndClearClientState, useLogout } from "@/app/(dashboard)/hooks/useLogout";
import { getLoginUrl } from "@/utils/returnUrlUtils";
import { Badge } from "@/components/ui/badge";
import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import Link from "next/link";
import React from "react";
import { cn } from "@/lib/cva.config";
import { NotificationsBell } from "./Navbar/NotificationsBell/NotificationsBell";
import { BellResources, InlineResourceLinks } from "./TopBar/ResourceLinks";
import UserDropdown from "./Navbar/UserDropdown/UserDropdown";
import ViewSwitcher from "./Navbar/ViewSwitcher";
import WorkerDropdown from "./Navbar/WorkerDropdown/WorkerDropdown";

interface NavbarProps {
  accessToken: string | null;
  isPublicPage: boolean;
  sidebarCollapsed?: boolean;
  onToggleSidebar?: () => void;
  deploymentHealth?: React.ReactNode;
}

const NAV_LOGO_CLASS_NAME = "h-auto max-h-full w-auto max-w-full object-contain";

const Navbar: React.FC<NavbarProps> = ({
  accessToken,
  isPublicPage = false,
  sidebarCollapsed = false,
  onToggleSidebar,
  deploymentHealth,
}) => {
  const baseUrl = getProxyBaseUrl();
  const { logoUrl, logoUrlDark } = useTheme();
  const { data: healthData } = useHealthReadinessDetails(accessToken);
  const version = healthData?.litellm_version;
  const disableBouncingIcon = useDisableBouncingIcon();
  const { isControlPlane, selectedWorker } = useWorker();
  const showWorkerSwitch = isControlPlane && selectedWorker !== null;

  const imageUrl = logoUrl || `${baseUrl}/get_image`;
  const darkImageUrl = logoUrlDark || logoUrl || `${baseUrl}/get_image?theme=dark`;

  const handleLogout = useLogout(accessToken);

  const handleWorkerSwitch = (workerId: string) => {
    void revokeSessionAndClearClientState(accessToken).finally(() => {
      window.location.href = `${getLoginUrl()}?worker=${encodeURIComponent(workerId)}`;
    });
  };

  return (
    <nav className="sticky top-0 z-chrome border-b border-border bg-card">
      <div className="w-full">
        <div className={cn("flex h-14 items-center px-4", isPublicPage && "gap-4 sm:px-6")}>
          <div className="flex shrink-0 items-center">
            {onToggleSidebar && (
              <button
                onClick={onToggleSidebar}
                className="mr-2 flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                <span className="text-lg">
                  {sidebarCollapsed ? (
                    <PanelLeftOpen className="size-[18px]" />
                  ) : (
                    <PanelLeftClose className="size-[18px]" />
                  )}
                </span>
              </button>
            )}

            <div className="flex items-center gap-2">
              <Link href={uiHref("")} className="flex items-center">
                <div className="relative">
                  <div
                    className={cn(
                      "flex h-10 max-w-48 items-center justify-center overflow-hidden",
                      isPublicPage && "h-8 max-w-36 sm:h-10 sm:max-w-48",
                    )}
                  >
                    <img src={imageUrl} alt="LiteLLM Brand" className={cn(NAV_LOGO_CLASS_NAME, "dark:hidden")} />
                    <img
                      src={darkImageUrl}
                      alt=""
                      aria-hidden
                      className={cn(NAV_LOGO_CLASS_NAME, "hidden dark:block")}
                    />
                  </div>
                </div>
              </Link>
              {version && (
                <div className="relative max-md:hidden">
                  {!disableBouncingIcon && (
                    <span
                      className="absolute -left-2 -top-1 animate-bounce text-lg"
                      style={{ animationDuration: "2s" }}
                      title="Thanks for using LiteLLM!"
                    >
                      🌑
                    </span>
                  )}
                  <Badge variant="outline" className="relative z-raised cursor-pointer text-xs font-medium">
                    <a
                      href="https://docs.litellm.ai/release_notes"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0"
                    >
                      v{version}
                    </a>
                  </Badge>
                </div>
              )}
            </div>
          </div>

          {!isPublicPage && (
            <div className="ml-4 flex shrink-0 items-center border-l border-border pl-4 max-md:hidden">
              <ViewSwitcher />
            </div>
          )}

          <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-4">
            {showWorkerSwitch && (
              <div className="flex shrink-0 items-center">
                <WorkerDropdown onWorkerSwitch={handleWorkerSwitch} />
              </div>
            )}

            <InlineResourceLinks textLinks={false} className="hidden md:flex" />

            {!isPublicPage && (
              <div className="flex shrink-0 items-center border-l border-border pl-4">
                <div className="flex items-center gap-1">
                  {deploymentHealth}
                  <NotificationsBell accessToken={accessToken} footer={<BellResources />} />
                  <span className="mx-1 h-5 w-px shrink-0 bg-border" aria-hidden />
                  <UserDropdown onLogout={handleLogout} />
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
