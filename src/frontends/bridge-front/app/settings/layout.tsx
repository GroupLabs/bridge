'use client'
import React from 'react';
import Link from "next/link"
import { usePathname } from "next/navigation"

interface SettingsLayoutProps {
  children: React.ReactNode;
}

export default function SettingsLayout({ children }: SettingsLayoutProps) {
  const pathname = usePathname()
  const isActive = (path: string) => pathname === path

  return (
    <div className="flex min-h-screen ">
      {/* Sidebar */}
      <aside className="w-64 p-6">
        <nav className="space-y-2">
          <Link
            href="/settings"
            className={`block py-2 px-4 rounded transition-colors ${isActive('/settings') ? 'bg-input text-white' : 'hover:bg-primary/5'}`}
          >
            General
          </Link>
          <Link
            href="/settings/integrations"
            className={`block py-2 px-4 rounded transition-colors ${isActive('/settings/integrations') ? 'bg-input text-white' : 'hover:bg-primary/5'}`}
          >
            Integrations
          </Link>
        </nav>
      </aside>

      {/* Main content */}
      <main className="flex-1 py-8">
        <div className="max-w-3xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  )
}