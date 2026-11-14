import { describe, expect, it } from "vitest";
import { ROLE_VIEWS, rolesSettled, viewFor } from "./roles";
import type { Role } from "./types";

const roles: Role[] = [
  { name: "Program leader", sections: ["decision"], detail: "summary", explain_terms: true, view: "story" },
  { name: "Researcher", sections: ["claims"], detail: "full", explain_terms: false, view: "evidence" },
  { name: "Hand edited", sections: ["claims"], detail: "standard", explain_terms: false, view: "bogus" as Role["view"] },
];

describe("viewFor", () => {
  it("falls back to checklist while roles are not loaded", () => {
    expect(viewFor(null, "Anyone")).toBe("checklist");
  });

  it("returns the view of a known role", () => {
    expect(viewFor(roles, "Program leader")).toBe("story");
    expect(viewFor(roles, "Researcher")).toBe("evidence");
  });

  it("falls back to checklist for a role that no longer exists", () => {
    expect(viewFor(roles, "Deleted role")).toBe("checklist");
  });

  it("falls back to checklist when the stored view is not one of the four", () => {
    expect(viewFor(roles, "Hand edited")).toBe("checklist");
  });
});

describe("ROLE_VIEWS", () => {
  it("lists the four views with labels and descriptions", () => {
    expect(ROLE_VIEWS.map((v) => v.id)).toEqual(["story", "checklist", "evidence", "raw"]);
    expect(ROLE_VIEWS.map((v) => v.label)).toEqual(["Story", "Checklist", "Evidence", "Raw data"]);
    for (const view of ROLE_VIEWS) expect(view.description.length).toBeGreaterThan(0);
  });
});

describe("rolesSettled", () => {
  it("is false while the roles load, true once they load or fail", () => {
    expect(rolesSettled(null, null)).toBe(false);
    expect(rolesSettled(roles, null)).toBe(true);
    expect(rolesSettled(null, "API down")).toBe(true);
    expect(rolesSettled([], null)).toBe(true);
  });
});
