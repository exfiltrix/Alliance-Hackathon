import { CrashTestIcon, PassportIcon, SealIcon, VerifyIcon } from "@/components/icons";

export const FLOW = [
  { key: "seal", href: "/seal", icon: SealIcon },
  { key: "verify", href: "/verify", icon: VerifyIcon },
  { key: "crash", href: "/crash-test", icon: CrashTestIcon },
  // Passport pages need an id, so this step starts from the crash test.
  { key: "passport", href: "/crash-test", icon: PassportIcon },
] as const;

export type FlowKey = (typeof FLOW)[number]["key"];
