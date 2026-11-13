"use client";

import { RotateCcw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAudit } from "@/lib/audit-context";
import { buttonQuiet } from "@/lib/ui";

/**
 * A quiet "Start over" control for the shell. Asks inline before clearing (no browser confirm()),
 * then empties the audit state and its sessionStorage copy and returns to the Start page.
 * Focus moves to the safe answer (Cancel) when the question opens, and back to the control when it is dismissed.
 */
export default function StartOver() {
  const router = useRouter();
  const { reset } = useAudit();
  const [asking, setAsking] = useState(false);
  const openerRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const returnFocus = useRef(false);

  useEffect(() => {
    if (asking) {
      cancelRef.current?.focus();
    } else if (returnFocus.current) {
      returnFocus.current = false;
      openerRef.current?.focus();
    }
  }, [asking]);

  function cancel() {
    returnFocus.current = true;
    setAsking(false);
  }

  if (!asking) {
    return (
      <button ref={openerRef} type="button" onClick={() => setAsking(true)} className={buttonQuiet}>
        <RotateCcw aria-hidden="true" className="size-4" />
        Start over
      </button>
    );
  }

  return (
    <div
      role="group"
      aria-label="Confirm start over"
      onKeyDown={(event) => {
        if (event.key === "Escape") cancel();
      }}
      className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm"
    >
      <span className="text-ink">Clear this audit?</span>
      <button
        type="button"
        onClick={() => {
          reset();
          setAsking(false);
          router.push("/start");
        }}
        className={buttonQuiet}
      >
        Yes, start over
      </button>
      <button ref={cancelRef} type="button" onClick={cancel} className={`${buttonQuiet} text-ink-soft`}>
        Cancel
      </button>
    </div>
  );
}
