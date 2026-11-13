import Link from "next/link";

/** SecondOpinion mark: a page of text with one line struck through and its correction written beneath. */
export default function Wordmark() {
  return (
    <Link
      href="/"
      className="inline-flex min-h-11 items-center gap-2.5 rounded-control focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-pen"
    >
      <svg viewBox="0 0 32 32" aria-hidden="true" className="size-8 shrink-0">
        <rect x="4" y="3" width="24" height="26" rx="3" fill="var(--color-sheet)" stroke="var(--color-ink)" strokeWidth="2" />
        <path d="M9 10h14" stroke="var(--color-rule-strong)" strokeWidth="2" strokeLinecap="round" />
        <path d="M9 16h14" stroke="var(--color-contradicted)" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M9 22h9" stroke="var(--color-supported)" strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      <span className="text-lg font-semibold tracking-tight text-ink">SecondOpinion</span>
    </Link>
  );
}
