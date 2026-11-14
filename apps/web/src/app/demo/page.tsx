import type { Metadata } from "next";
import Storyboard from "@/components/storyboard/Storyboard";

export const metadata: Metadata = {
  title: "Watch an audit | SecondOpinion",
  description: "The whole audit played as a storyboard: the report, the recount, each verdict, the review and the decision.",
};

export default function DemoPage() {
  return <Storyboard />;
}
