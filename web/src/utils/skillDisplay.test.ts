import { describe, it, expect } from "vitest";

import {
  buildDisplayDecisions,
  effectiveSkillName,
  groupSkillsForDisplay,
  type EditableProposalGroup,
} from "./skillDisplay";
import type { GitHubSkillItem } from "../api/types";

function skill(overrides: Partial<GitHubSkillItem>): GitHubSkillItem {
  return {
    kind: "package",
    canonical_name: "x",
    ecosystem: "npm",
    parent: null,
    display_name: null,
    confirmed_display_name: null,
    group_id: null,
    decision_source: null,
    decision_reviewed: false,
    evidence: [],
    proficiency: null,
    ...overrides,
  } as GitHubSkillItem;
}

describe("effectiveSkillName", () => {
  it("確定表示名 > 機械 display_name > canonical の順で解決する", () => {
    expect(
      effectiveSkillName(
        skill({ canonical_name: "hcl", display_name: "Terraform", confirmed_display_name: "IaC" }),
      ),
    ).toBe("IaC");
    expect(
      effectiveSkillName(skill({ canonical_name: "hcl", display_name: "Terraform" })),
    ).toBe("Terraform");
    expect(effectiveSkillName(skill({ canonical_name: "react" }))).toBe("react");
  });
});

describe("groupSkillsForDisplay", () => {
  it("同一 group_id のスキルを 1 グループへ畳み、未確定は単独グループにする", () => {
    const skills = [
      skill({ canonical_name: "@aws-sdk/client-s3", group_id: "g1", confirmed_display_name: "AWS SDK" }),
      skill({ canonical_name: "@aws-sdk/client-sns", group_id: "g1", confirmed_display_name: "AWS SDK" }),
      skill({ canonical_name: "react", group_id: null }),
    ];
    const groups = groupSkillsForDisplay(skills);
    expect(groups).toHaveLength(2);
    const aws = groups.find((g) => g.label === "AWS SDK");
    expect(aws?.skills).toHaveLength(2);
    const react = groups.find((g) => g.label === "react");
    expect(react?.skills).toHaveLength(1);
  });
});

describe("buildDisplayDecisions", () => {
  const proposal: EditableProposalGroup[] = [
    {
      displayName: "AWS SDK",
      originalDisplayName: "AWS SDK",
      members: [
        { kind: "package", ecosystem: "npm", canonical_name: "@aws-sdk/client-s3" },
        { kind: "package", ecosystem: "npm", canonical_name: "@aws-sdk/client-sns" },
      ],
    },
    {
      displayName: "React",
      originalDisplayName: "react",
      members: [{ kind: "package", ecosystem: "npm", canonical_name: "react" }],
    },
  ];

  it("複数メンバーのグループは共通 group_id を割り当て、単独は group_id なし", () => {
    const decisions = buildDisplayDecisions(proposal);
    const aws = decisions.filter((d) => d.display_name === "AWS SDK");
    expect(aws).toHaveLength(2);
    expect(aws[0].group_id).toBeTruthy();
    expect(aws[0].group_id).toBe(aws[1].group_id); // 同一グループは同じ id を共有
    const react = decisions.find((d) => d.display_name === "React");
    expect(react?.group_id).toBeNull(); // 単独は null
  });

  it("表示名を編集していなければ source=agent、編集していれば human", () => {
    const decisions = buildDisplayDecisions(proposal);
    expect(decisions.find((d) => d.display_name === "AWS SDK")?.source).toBe("agent");
    // "react" → "React" に編集したので human
    expect(decisions.find((d) => d.display_name === "React")?.source).toBe("human");
  });

  it("表示名が空のグループは確定対象から除外する（切り詰めない）", () => {
    const decisions = buildDisplayDecisions([
      {
        displayName: "   ",
        originalDisplayName: "",
        members: [{ kind: "package", ecosystem: "npm", canonical_name: "react" }],
      },
    ]);
    expect(decisions).toHaveLength(0);
  });
});
