import { Calculator, Gauge, PenLine, UserCheck } from "lucide-react";
import Section from "./Section";
import { Stagger, StaggerItem } from "./motion";

const POINTS = [
  {
    icon: Calculator,
    title: "Each figure recounted from the data",
    text: "Ordinary code counts the release and compares the result with the report’s figure. The calculation is shown, so every number can be traced.",
    span: "md:col-span-3",
  },
  {
    icon: Gauge,
    title: "How firm each answer is",
    text: "Every count is repeated under the other reasonable choices. If the verdict holds under all of them it is robust; if it flips, it is fragile.",
    span: "md:col-span-3",
  },
  {
    icon: PenLine,
    title: "Wording the data supports",
    text: "What the data does not support is struck out and the supported version written beneath. Claims the data cannot speak to, such as treatment response, come back as insufficient evidence instead of a guess.",
    span: "md:col-span-4",
  },
  {
    icon: UserCheck,
    title: "The decision stays with you",
    text: "You confirm or override each verdict, record one decision, and export it as audit.json.",
    span: "md:col-span-2",
    accent: true,
  },
];

export default function WhatYouGet() {
  return (
    <Section id="what" title="What you get">
      <Stagger as="ul" className="grid gap-4 md:grid-cols-6">
        {POINTS.map((point) => (
          <StaggerItem
            key={point.title}
            as="li"
            lift
            className={`rounded-panel border p-5 transition-colors duration-200 sm:p-6 ${point.span} ${
              point.accent
                ? "border-blush bg-pen-tint hover:border-pen"
                : "border-rule bg-sheet hover:border-rule-strong"
            }`}
          >
            <span
              aria-hidden="true"
              className={`grid size-10 place-items-center rounded-control ${
                point.accent ? "bg-pen text-white" : "bg-pen-tint text-pen"
              }`}
            >
              <point.icon size={20} strokeWidth={1.75} />
            </span>
            <h3 className="mt-4 font-semibold text-ink">{point.title}</h3>
            <p className="mt-1.5 text-[0.9375rem] text-ink-soft">{point.text}</p>
          </StaggerItem>
        ))}
      </Stagger>
    </Section>
  );
}
