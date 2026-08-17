import { useLocation } from "react-router";
import { SettingsDesktopSidebar } from "./settings-desktop-sidebar";
import { SettingsNavRenderedItem } from "#/hooks/use-settings-nav-items";
import { settingsLayoutMainScrollClassName } from "#/utils/settings-like-page-layout-classes";
import { cn } from "#/utils/utils";

interface SettingsLayoutProps {
  children: React.ReactNode;
  navigationItems: SettingsNavRenderedItem[];
}

/**
 * Mirrors the extensions layout (Skills / MCP): aside and main are siblings,
 * and only the main column scrolls so the left nav stays pinned like
 * ExtensionsNavigation.
 */
export function SettingsLayout({
  children,
  navigationItems,
}: SettingsLayoutProps) {
  const { pathname } = useLocation();
  const isHostPage = pathname === "/settings/host";

  return (
    <div className="flex h-full flex-col md:pt-8">
      <div className="flex min-h-0 flex-1 gap-10 md:items-start">
        <SettingsDesktopSidebar navigationItems={navigationItems} />
        <main className={settingsLayoutMainScrollClassName}>
          <div
            className={cn(
              "mx-auto w-full min-w-0",
              isHostPage ? "max-w-none" : "max-w-[800px]",
            )}
          >
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
