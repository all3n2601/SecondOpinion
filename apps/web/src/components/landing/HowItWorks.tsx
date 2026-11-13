import Section from "./Section";

const STEPS = [
  {
    title: "Read the report",
    text: "SecondOpinion reads the report and pulls out the sentences that can be checked against data.",
  },
  {
    title: "Check each sentence",
    text: "Ordinary code checks each one against the data and shows the calculation, so every number can be traced.",
  },
  {
    title: "Recount eight ways",
    text: "Each answer is recounted eight reasonable ways. If it still holds it is robust; if it flips it is fragile.",
  },
  {
    title: "Decide and export",
    text: "A person confirms each verdict and records one decision. The result is exported as audit.json.",
  },
];

export default function HowItWorks() {
  return (
    <Section id="how" title="How it works">
      <ol role="list" className="grid gap-8 md:grid-cols-4 md:gap-6">
        {STEPS.map((step, index) => (
          <li key={step.title} className="border-t-2 border-ink pt-4">
            <span aria-hidden="true" className="num font-mono text-sm text-ink-soft">
              {index + 1}
            </span>
            <h3 className="mt-1 text-base font-semibold text-ink">{step.title}</h3>
            <p className="mt-2 text-[0.9375rem] text-ink-soft">{step.text}</p>
          </li>
        ))}
      </ol>
    </Section>
  );
}
