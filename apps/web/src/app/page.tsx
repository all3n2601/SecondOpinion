import FinishedPreview from "@/components/landing/FinishedPreview";
import Hero from "@/components/landing/Hero";
import HowItWorks from "@/components/landing/HowItWorks";
import Limits from "@/components/landing/Limits";
import OwnReportForm from "@/components/landing/OwnReportForm";
import Section from "@/components/landing/Section";

/** The front door, and still the tool's entry: hero with a one-click practice audit, then the form for your own report. */
export default function StartPage() {
  return (
    <main>
      <Hero />
      <HowItWorks />
      <FinishedPreview />
      <Limits />
      <div id="start">
        <Section
          id="own"
          title="Audit your own report"
          intro="Add the report and the data folder it describes. SecondOpinion then finds the claims for you to review."
        >
          <OwnReportForm />
        </Section>
      </div>
    </main>
  );
}
