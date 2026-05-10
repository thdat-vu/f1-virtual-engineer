"use client";

import { useState } from "react";
import { useSupabase } from "./SupabaseProvider";

const buttonClass =
  "shrink-0 rounded-sm border border-border-strong px-2 py-0.5 text-[length:var(--text-readout)] uppercase tracking-wide text-foreground-dim transition-colors duration-[var(--dur-fast)] hover:text-foreground hover:border-foreground disabled:opacity-40 disabled:cursor-not-allowed";

export function AuthButton() {
  const { supabase, session, configured } = useSupabase();
  const [busy, setBusy] = useState(false);

  if (!configured) {
    return (
      <button
        type="button"
        className={buttonClass}
        disabled
        title="Supabase env vars not configured"
      >
        Sign in unavailable
      </button>
    );
  }

  if (session) {
    const email = session.user.email ?? session.user.id;
    return (
      <div className="flex items-center gap-2">
        <span className="readout shrink-0 text-[length:var(--text-readout)] text-foreground-dim">
          {email}
        </span>
        <button
          type="button"
          className={buttonClass}
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await supabase!.auth.signOut();
            } finally {
              setBusy(false);
            }
          }}
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      aria-label="Sign in with Google"
      title="Sign in with Google"
      className="shrink-0 rounded-sm p-1 opacity-80 transition-opacity duration-[var(--dur-fast)] hover:opacity-100 disabled:opacity-40 disabled:cursor-not-allowed"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await supabase!.auth.signInWithOAuth({
            provider: "google",
            options: { redirectTo: `${window.location.origin}/auth/callback` },
          });
        } finally {
          setBusy(false);
        }
      }}
    >
      {/* Plain <img> keeps the bundle small; the SVG is in /public. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/icons/google/google-icon-logo-svgrepo-com.svg"
        alt=""
        width={20}
        height={20}
        className="block"
      />
    </button>
  );
}
