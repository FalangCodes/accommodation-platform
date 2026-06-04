"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Building2, Menu, X, Search } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Navbar() {
  const { user, logout, isLandlord, isModerator } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const router = useRouter();

  return (
    <nav className="sticky top-0 z-50 w-full bg-white border-b border-gray-100 shadow-sm">
      {/* w-full lets it breathe, but xl:px-24 pushes the logo and buttons inward by almost 100 pixels on each side */}
      <div className="w-full px-6 lg:px-16 xl:px-24">
        <div className="flex h-16 items-center justify-between relative">
          {/* ── Logo ── */}
          <Link
            href="/"
            className="flex items-center gap-2.5 shrink-0"
          >
            {/* Using bg-primary instead of hardcoded hex */}
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary">
              <Building2 className="h-5 w-5 text-white" />
            </div>
            <span className="text-[1.1rem] font-bold tracking-tight text-primary">
              AccomFind
            </span>
          </Link>

          {/* ── Center nav links (desktop) ── */}
          <div className="hidden md:flex items-center gap-8 absolute left-1/2 -translate-x-1/2">
            <Link
              href="/search"
              className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
            >
              Find accommodation
            </Link>
            {isLandlord && (
              <Link
                href="/dashboard"
                className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
              >
                My listings
              </Link>
            )}
            {isModerator && (
              <Link
                href="/admin"
                className="text-sm font-medium text-muted-foreground hover:text-primary transition-colors"
              >
                Moderation
              </Link>
            )}
          </div>

          {/* ── Right side actions (desktop) ── */}
          <div className="hidden md:flex items-center gap-3 shrink-0">
            {user ? (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-2.5 rounded-full border border-gray-200 pl-3 pr-2 py-1.5 hover:shadow-md transition-all duration-150 bg-white">
                    <span className="text-sm font-medium text-gray-700 max-w-[120px] truncate">
                      {user.email.split("@")[0]}
                    </span>
                    <Avatar className="h-7 w-7">
                      <AvatarFallback className="bg-[#1F4E79] text-white text-xs font-semibold">
                        {user.email[0].toUpperCase()}
                      </AvatarFallback>
                    </Avatar>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-52 mt-1">
                  <div className="px-3 py-2 border-b border-gray-100">
                    <p className="text-xs text-gray-400 uppercase tracking-wide font-medium">
                      Signed in as
                    </p>
                    <p className="text-sm font-semibold text-gray-800 truncate mt-0.5">
                      {user.email}
                    </p>
                    <span className="inline-block mt-1 text-xs bg-[#E6F1FB] text-[#1F4E79] font-medium px-2 py-0.5 rounded-full capitalize">
                      {user.role}
                    </span>
                  </div>
                  {isLandlord && (
                    <DropdownMenuItem asChild>
                      <Link href="/dashboard" className="cursor-pointer">
                        My listings
                      </Link>
                    </DropdownMenuItem>
                  )}
                  <DropdownMenuItem asChild>
                    <Link href="/profile" className="cursor-pointer">
                      Profile settings
                    </Link>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onClick={logout}
                    className="text-red-500 focus:text-red-600 focus:bg-red-50 cursor-pointer"
                  >
                    Sign out
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            ) : (
              <>
                <Link href="/login">
                  <Button
                    variant="ghost"
                    className="text-muted-foreground font-semibold hover:text-primary hover:bg-primary/5 px-5"
                  >
                    Sign in
                  </Button>
                </Link>
                <Link href="/register">
                  <Button
                    className="bg-primary hover:bg-primary/90 text-primary-foreground font-semibold px-6 rounded-full shadow-sm hover:shadow-md transition-all"
                  >
                    Get started
                  </Button>
                </Link>
              </>
            )}
          </div>

          {/* ── Mobile hamburger ── */}
          <button
            className="md:hidden p-2 rounded-lg hover:bg-gray-100 transition-colors"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label="Toggle menu"
          >
            {mobileOpen
              ? <X className="h-5 w-5 text-gray-600" />
              : <Menu className="h-5 w-5 text-gray-600" />
            }
          </button>

        </div>
      </div>

      {/* ── Mobile menu ── */}
      {mobileOpen && (
        <div className="md:hidden border-t border-gray-100 bg-white px-6 py-4">
          <div className="flex flex-col gap-4">
            <Link
              href="/search"
              className="text-sm font-medium text-gray-600"
              onClick={() => setMobileOpen(false)}
            >
              Find accommodation
            </Link>
            {isLandlord && (
              <Link
                href="/dashboard"
                className="text-sm font-medium text-gray-600"
                onClick={() => setMobileOpen(false)}
              >
                My listings
              </Link>
            )}
            {isModerator && (
              <Link
                href="/admin"
                className="text-sm font-medium text-gray-600"
                onClick={() => setMobileOpen(false)}
              >
                Moderation
              </Link>
            )}
            <div className="pt-2 border-t border-gray-100">
              {user ? (
                <div className="flex flex-col gap-3">
                  <div>
                    <p className="text-xs text-gray-400">Signed in as</p>
                    <p className="text-sm font-semibold text-gray-800">{user.email}</p>
                  </div>
                  <button
                    onClick={logout}
                    className="text-left text-sm font-medium text-red-500"
                  >
                    Sign out
                  </button>
                </div>
              ) : (
                <div className="flex gap-3">
                  <Link href="/login" onClick={() => setMobileOpen(false)}>
                    <Button variant="outline" size="sm" className="rounded-full">
                      Sign in
                    </Button>
                  </Link>
                  <Link href="/register" onClick={() => setMobileOpen(false)}>
                    <Button
                      size="sm"
                      className="bg-[#1F4E79] text-white rounded-full"
                    >
                      Get started
                    </Button>
                  </Link>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}