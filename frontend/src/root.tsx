import {
  Links,
  Meta,
  MetaFunction,
  Outlet,
  Scripts,
  ScrollRestoration,
} from "react-router";
import "./tailwind.css";
import "./index.css";
import React from "react";
import { Toaster } from "react-hot-toast";
import { useInvitation } from "#/hooks/use-invitation";
import { LoadingSpinner } from "#/components/shared/loading-spinner";

export function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href={`${import.meta.env.BASE_URL}favicon.ico`} />
        <Meta />
        <Links />
      </head>
      <body>
        {children}
        <ScrollRestoration />
        <Scripts />
        <Toaster />
        <div id="modal-portal-exit" />
      </body>
    </html>
  );
}

export const meta: MetaFunction = () => [
  { title: "Creanova" },
  { name: "description", content: "Let's Start Building!" },
];

export function HydrateFallback() {
  return (
    <div className="flex h-screen items-center justify-center bg-[#0d0f12]">
      <LoadingSpinner size="large" />
    </div>
  );
}

export default function App() {
  // Handle invitation token cleanup when invitation flow completes
  // This runs on all pages to catch redirects from auth callback
  useInvitation();

  return <Outlet />;
}
