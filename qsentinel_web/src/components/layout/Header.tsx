"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Shield, Activity, Layers, Terminal, AlertTriangle } from "lucide-react";

export function Header({ isHealthy, isReady }: { isHealthy: boolean; isReady: boolean }) {
  const pathname = usePathname();

  return (
    <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <Link href="/" className="flex items-center gap-3">
            <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <span className="font-bold tracking-tight text-zinc-100 text-lg">QSENTINEL</span>
              <span className="ml-2 text-xs font-mono text-zinc-500 uppercase tracking-widest">
                v1.0.0
              </span>
            </div>
          </Link>

          <nav className="hidden md:flex items-center gap-1">
            <Link
              href="/"
              className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                pathname === "/"
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
              }`}
            >
              <Activity className="w-4 h-4 inline mr-2" />
              Command Center
            </Link>
            <Link
              href="/streams"
              className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                pathname.startsWith("/streams")
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900"
              }`}
            >
              <Layers className="w-4 h-4 inline mr-2" />
              Streams
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-3 text-xs font-mono">
            <div className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  isHealthy ? "bg-emerald-500 animate-pulse" : "bg-red-500"
                }`}
              />
              <span className="text-zinc-400">LIVENESS:</span>
              <span className={isHealthy ? "text-emerald-400" : "text-red-400"}>
                {isHealthy ? "OK" : "DOWN"}
              </span>
            </div>

            <div className="flex items-center gap-1.5 border-l border-zinc-800 pl-3">
              <span
                className={`w-2 h-2 rounded-full ${
                  isReady ? "bg-emerald-500" : "bg-yellow-500"
                }`}
              />
              <span className="text-zinc-400">DB:</span>
              <span className={isReady ? "text-emerald-400" : "text-yellow-400"}>
                {isReady ? "CONNECTED" : "UNREADY"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
