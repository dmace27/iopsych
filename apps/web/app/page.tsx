import { redirect } from "next/navigation";

/** Send the application root to the internal role workspace. */
export default function Home(): never {
  redirect("/roles");
}
