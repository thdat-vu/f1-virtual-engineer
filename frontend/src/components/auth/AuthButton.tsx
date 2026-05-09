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
      className={buttonClass}
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
      Sign in with Google
    </button>
  );
}
