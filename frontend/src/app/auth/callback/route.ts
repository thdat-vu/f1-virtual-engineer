import { NextResponse } from "next/server";
import { createSupabaseServerClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const nextParam = url.searchParams.get("next");

  // Only honour same-origin redirects to avoid open-redirect.
  const redirectPath =
    nextParam && nextParam.startsWith("/") && !nextParam.startsWith("//")
      ? nextParam
      : "/mission-control";

  if (!code) {
    return NextResponse.redirect(new URL(redirectPath, url.origin));
  }

  const supabase = await createSupabaseServerClient();
  if (!supabase) {
    return NextResponse.redirect(new URL(redirectPath, url.origin));
  }

  await supabase.auth.exchangeCodeForSession(code);
  return NextResponse.redirect(new URL(redirectPath, url.origin));
}
