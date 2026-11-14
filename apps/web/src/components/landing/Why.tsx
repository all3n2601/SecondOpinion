import Section from "./Section";
import { Stagger, StaggerItem } from "./motion";

/** The problem, in plain prose: figures in reports are repeated, rarely recounted, and depend on how you count. */
export default function Why() {
  return (
    <Section id="why" title="Why recount a report?">
      <Stagger className="max-w-prose space-y-5 text-[1.0625rem] sm:text-lg sm:leading-8">
        <StaggerItem>
          <p>
            A report says Luminal A makes up about 62% of tumors. It reads like a fact, and it gets repeated like one.
            Checking it means finding the right release, deciding which samples belong, and redoing the arithmetic, so
            most figures are taken as written.
          </p>
        </StaggerItem>
        <StaggerItem>
          <p>
            The answer also depends on small choices: which subtype label to use, whether to filter by sex, which
            samples count. A figure can hold under one choice and fall apart under another, and the sentence does not
            say which was used.
          </p>
        </StaggerItem>
        <StaggerItem>
          <p className="font-semibold text-ink">SecondOpinion does the recount for you and shows how it got there.</p>
        </StaggerItem>
      </Stagger>
    </Section>
  );
}
