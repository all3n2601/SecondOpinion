import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import FinishedPreview from "@/components/landing/FinishedPreview";
import Hero from "@/components/landing/Hero";
import HowItWorks from "@/components/landing/HowItWorks";
import Limits from "@/components/landing/Limits";
import Section from "@/components/landing/Section";
import { buttonPrimary } from "@/lib/ui";

/** The front door: what the tool does and what it can't, then on to /start for the audit itself. */
export default function LandingPage() {
  return (
    <main>
      <Hero />
      <HowItWorks />
      <FinishedPreview />
      <Limits />
      <Section
        id="begin"
        title="Audit a report"
        intro="Bring a report and the TCGA-BRCA data folder it describes, or run the practice report to see the whole audit first."
      >
        <Link href="/start" className={buttonPrimary}>
          <ClipboardCheck aria-hidden="true" size={18} strokeWidth={1.75} />
          Start an audit
        </Link>
      </Section>
    </main>
  );
}
