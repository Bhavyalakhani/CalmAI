"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Brain,
  BookOpen,
  LineChart,
  MessageSquare,
  Settings,
  LogOut,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import type { Patient } from "@/types";

const navItems = [
  { href: "/journal", label: "Journal", icon: BookOpen },
  { href: "/journal/insights", label: "Insights", icon: LineChart },
  { href: "/journal/prompts", label: "Prompts", icon: MessageSquare },
  { href: "/journal/settings", label: "Settings", icon: Settings },
];

export default function JournalLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const patient = user as Patient | null;

  const initials = patient?.name
    ? patient.name
        .split(" ")
        .map((n) => n[0])
        .join("")
    : "?";

  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* top nav */}
      <header className="sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-6">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2">
              <Brain className="h-5 w-5" />
              <span className="text-sm font-bold tracking-tight">CalmAI</span>
            </Link>

            <nav className="flex items-center gap-1">
              {navItems.map((item) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/journal" &&
                    pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-muted text-foreground"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    )}
                  >
                    <item.icon className="h-3.5 w-3.5" />
                    {item.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-[10px]">{initials}</AvatarFallback>
              </Avatar>
              <span className="text-sm font-medium">{patient?.name ?? "Patient"}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={logout}>
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* page content */}
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-8">
        {children}
      </main>
    </div>
  );
}
