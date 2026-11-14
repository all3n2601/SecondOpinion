import FinalCta from "@/components/landing/FinalCta";
import FinishedPreview from "@/components/landing/FinishedPreview";
import Hero from "@/components/landing/Hero";
import LandingBar from "@/components/landing/LandingBar";
import Limits from "@/components/landing/Limits";
import { LandingMotion, ScrollProgress } from "@/components/landing/motion";
import WhatYouGet from "@/components/landing/WhatYouGet";
import Why from "@/components/landing/Why";

/**
 * The front door: the problem, what you get, an example and the limits. No steps here; "Start an audit"
 * opens /start, where the step rail and the pipeline appear.
 */
export default function LandingPage() {
  return (
    <LandingMotion>
      <ScrollProgress />
      <LandingBar />
      <main>
        <Hero />
        <Why />
        <WhatYouGet />
        <FinishedPreview />
        <Limits />
        <FinalCta />
      </main>
    </LandingMotion>
  );
}
