import { Stagger, StaggerItem } from "./motion";
import Section from "./Section";

const LIMITS = [
  {
    lead: "It checks one release.",
    text: "Claims are compared with the TCGA-BRCA release you supply, and nothing else.",
  },
  {
    lead: "There are no treatment or response records.",
    text: "A claim about what a treatment did can only come back as insufficient evidence.",
  },
  {
    lead: "Subtype calls exist for 844 of 1,101 primary tumors.",
    text: "Claims about subtypes are counted against those 844.",
  },
  {
    lead: "A person reviews every verdict.",
    text: "The tool proposes an answer and shows its work. You confirm or override it.",
  },
  {
    lead: "It is a research prototype.",
    text: "It is not clinical advice, and it should not guide care or treatment decisions.",
  },
];

export default function Limits() {
  return (
    <Section id="limits" title="What this can’t tell you">
      <Stagger as="ul" className="max-w-prose divide-y divide-rule border-y border-rule">
        {LIMITS.map((item) => (
          <StaggerItem as="li" key={item.lead} className="py-4">
            <span className="font-semibold text-ink">{item.lead}</span>{" "}
            <span className="text-ink-soft">{item.text}</span>
          </StaggerItem>
        ))}
      </Stagger>
    </Section>
  );
}
