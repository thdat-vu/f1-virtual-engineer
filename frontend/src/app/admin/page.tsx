import { redirect } from "next/navigation";

// Old admin URL — kept so existing bookmarks / screenshots / links land
// on the new public observability page instead of a 404. Safe to remove
// once external traffic to /admin drops to zero.
export default function AdminRedirect() {
  redirect("/observability");
}
