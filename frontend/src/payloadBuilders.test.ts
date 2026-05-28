import { describe, it, expect } from "vitest";

import {
  buildCareerPayload,
  hasAnyText,
  validateDateRange,
  type CareerClientForm,
  type CareerExperienceForm,
  type CareerFormState,
  type CareerProjectForm,
  type CareerProjectPeriodForm,
} from "./payloadBuilders";

// ── 共通 fixture ────────────────────────────────────────────────

const blankPeriod = (overrides: Partial<CareerProjectPeriodForm> = {}): CareerProjectPeriodForm => ({
  start_date: "2024-01",
  end_date: "2024-06",
  is_current: false,
  ...overrides,
});

const blankProject = (overrides: Partial<CareerProjectForm> = {}): CareerProjectForm => ({
  name: "P",
  periods: [blankPeriod()],
  role: "",
  description: "",
  team: { total: "", members: [] },
  technology_stacks: [],
  phases: [],
  ...overrides,
});

const blankClient = (overrides: Partial<CareerClientForm> = {}): CareerClientForm => ({
  name: "",
  has_client: true,
  projects: [],
  is_vacation: false,
  vacation_start_date: "",
  vacation_end_date: "",
  vacation_is_current: false,
  vacation_description: "",
  ...overrides,
});

const blankExperience = (overrides: Partial<CareerExperienceForm> = {}): CareerExperienceForm => ({
  company: "Acme",
  business_description: "Web",
  start_date: "2023-01",
  end_date: "2024-01",
  is_current: false,
  employee_count: "",
  capital: "",
  capital_unit: "千万円",
  is_it_company: true,
  description: "",
  clients: [],
  ...overrides,
});

const baseState = (overrides: Partial<CareerFormState> = {}): CareerFormState => ({
  full_name: "山田 太郎",
  career_summary: "要約",
  self_pr: "自己PR",
  experiences: [],
  qualifications: [],
  ...overrides,
});

// ── validateDateRange ────────────────────────────────────────────

describe("validateDateRange", () => {
  it("開始日が終了日より後の場合にエラーメッセージが返される", () => {
    const error = validateDateRange("2024-06", "2024-01", false);
    expect(error).not.toBeNull();
    expect(error).toContain("開始日");
  });

  it("開始日と終了日が同じ場合はエラーにならない", () => {
    expect(validateDateRange("2024-01", "2024-01", false)).toBeNull();
  });

  it("開始日が終了日より前の場合はエラーにならない", () => {
    expect(validateDateRange("2024-01", "2024-12", false)).toBeNull();
  });

  it("is_current が true の場合は終了日が不正でもエラーにならない", () => {
    expect(validateDateRange("2024-06", "2024-01", true)).toBeNull();
  });

  it("開始日または終了日が空の場合はエラーにならない", () => {
    expect(validateDateRange("", "2024-01", false)).toBeNull();
    expect(validateDateRange("2024-01", "", false)).toBeNull();
  });
});

// ── hasAnyText ──────────────────────────────────────────────────

describe("hasAnyText", () => {
  it("すべて空 / null / undefined / 空白のみなら false を返す", () => {
    expect(hasAnyText([])).toBe(false);
    expect(hasAnyText([""])).toBe(false);
    expect(hasAnyText([null, undefined])).toBe(false);
    expect(hasAnyText(["   ", "\t", "\n"])).toBe(false);
  });

  it("1 つでも非空白文字を含めば true を返す", () => {
    expect(hasAnyText(["", " x "])).toBe(true);
    expect(hasAnyText([null, "a"])).toBe(true);
    expect(hasAnyText(["foo"])).toBe(true);
  });
});

// ── buildCareerPayload: 基本 ───────────────────────────────────

describe("buildCareerPayload (basic validation)", () => {
  it("氏名が空ならエラー", () => {
    expect(() => buildCareerPayload(baseState({ full_name: "  " }))).toThrow(/氏名/);
  });

  it("職務要約が空ならエラー", () => {
    expect(() => buildCareerPayload(baseState({ career_summary: "" }))).toThrow(/職務要約/);
  });

  it("自己PR が空ならエラー", () => {
    expect(() => buildCareerPayload(baseState({ self_pr: "" }))).toThrow(/自己PR/);
  });

  it("必須項目が揃えば experiences/qualifications 空でも payload を返す", () => {
    const payload = buildCareerPayload(baseState());
    expect(payload.full_name).toBe("山田 太郎");
    expect(payload.experiences).toEqual([]);
    expect(payload.qualifications).toEqual([]);
  });

  it("前後の空白は trim される", () => {
    const payload = buildCareerPayload(
      baseState({ full_name: "  山田  ", career_summary: " 要約 ", self_pr: " PR " }),
    );
    expect(payload.full_name).toBe("山田");
    expect(payload.career_summary).toBe("要約");
    expect(payload.self_pr).toBe("PR");
  });
});

// ── experiences の境界 ────────────────────────────────────────

describe("buildCareerPayload (experiences)", () => {
  it("is_current=true の experience は end_date が空文字に正規化される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [blankExperience({ is_current: true, end_date: "2024-12" })],
      }),
    );
    expect(payload.experiences[0].end_date).toBe("");
    expect(payload.experiences[0].is_current).toBe(true);
  });

  it("is_current=false で end_date 空ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [blankExperience({ is_current: false, end_date: "  " })],
        }),
      ),
    ).toThrow(/離職年月/);
  });

  it("start_date より end_date が前ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [blankExperience({ start_date: "2024-06", end_date: "2024-01" })],
        }),
      ),
    ).toThrow(/開始日/);
  });

  it("会社名や事業内容が空ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [blankExperience({ company: "", business_description: "" })],
        }),
      ),
    ).toThrow(/会社名/);
  });

  it("capital_unit が payload にそのまま引き継がれる", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [blankExperience({ capital: "5", capital_unit: "百万円" })],
      }),
    );
    expect(payload.experiences[0].capital).toBe("5");
    expect(payload.experiences[0].capital_unit).toBe("百万円");
  });

  it("空欄だけの experience は filter で除外され、エラーにならない", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            company: "",
            business_description: "",
            start_date: "",
            end_date: "",
          }),
        ],
      }),
    );
    expect(payload.experiences).toEqual([]);
  });
});

// ── projects / clients / team の境界 ─────────────────────────

describe("buildCareerPayload (projects/clients/team)", () => {
  it("project の period.is_current=true なら end_date が空文字に正規化される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                name: "顧客A",
                has_client: true,
                projects: [
                  blankProject({
                    periods: [blankPeriod({ is_current: true, end_date: "2024-12" })],
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
    );
    const period = payload.experiences[0].clients[0].projects[0].periods[0];
    expect(period.end_date).toBe("");
    expect(period.is_current).toBe(true);
  });

  it("内容のある project で期間の開始年月が空ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [
            blankExperience({
              clients: [
                blankClient({
                  name: "顧客A",
                  has_client: true,
                  projects: [blankProject({ periods: [blankPeriod({ start_date: "" })] })],
                }),
              ],
            }),
          ],
        }),
      ),
    ).toThrow(/プロジェクトの開始年月/);
  });

  it("内容のある project に period が 1 件も無いならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [
            blankExperience({
              clients: [
                blankClient({
                  name: "顧客A",
                  has_client: true,
                  projects: [blankProject({ name: "P", description: "詳細", periods: [] })],
                }),
              ],
            }),
          ],
        }),
      ),
    ).toThrow(/プロジェクトの開始年月/);
  });

  it("project の period が is_current=false で終了年月が空ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [
            blankExperience({
              clients: [
                blankClient({
                  name: "顧客A",
                  has_client: true,
                  projects: [
                    blankProject({ periods: [blankPeriod({ is_current: false, end_date: "" })] }),
                  ],
                }),
              ],
            }),
          ],
        }),
      ),
    ).toThrow(/プロジェクトの終了年月/);
  });

  it("client.has_client=false なら name が空文字に正規化される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                name: "捨てられる",
                has_client: false,
                projects: [blankProject()],
              }),
            ],
          }),
        ],
      }),
    );
    expect(payload.experiences[0].clients[0].name).toBe("");
    expect(payload.experiences[0].clients[0].has_client).toBe(false);
  });

  it("client.has_client=true で name 空かつ projects が中身なしなら除外される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                name: "",
                has_client: true,
                projects: [],
              }),
            ],
          }),
        ],
      }),
    );
    expect(payload.experiences[0].clients).toEqual([]);
  });

  it("team.members の空配列は payload でも空配列のまま", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                name: "C",
                has_client: true,
                projects: [blankProject({ team: { total: "3", members: [] } })],
              }),
            ],
          }),
        ],
      }),
    );
    expect(payload.experiences[0].clients[0].projects[0].team.members).toEqual([]);
    expect(payload.experiences[0].clients[0].projects[0].team.total).toBe("3");
  });

  it("team.members は role と count が両方 truthy のものだけ残り、count は number 化される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                name: "C",
                has_client: true,
                projects: [
                  blankProject({
                    team: {
                      total: "",
                      members: [
                        { role: "PM", count: "1" },
                        { role: "", count: "2" }, // role 空 → 除外
                        { role: "SE", count: "" }, // count 空 → 除外
                        { role: "QA", count: "3" },
                      ],
                    },
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
    );
    const members = payload.experiences[0].clients[0].projects[0].team.members;
    expect(members).toEqual([
      { role: "PM", count: 1 },
      { role: "QA", count: 3 },
    ]);
  });

  it("technology_stacks は name が空のものを除外する", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                name: "C",
                has_client: true,
                projects: [
                  blankProject({
                    technology_stacks: [
                      { category: "language", name: "TypeScript" },
                      { category: "framework", name: "  " },
                      { category: "db", name: "PostgreSQL" },
                    ],
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
    );
    const stacks = payload.experiences[0].clients[0].projects[0].technology_stacks;
    expect(stacks).toEqual([
      { category: "language", name: "TypeScript" },
      { category: "db", name: "PostgreSQL" },
    ]);
  });

  it("project の name が空で description に内容があればプロジェクトはペイロードに含まれる", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                name: "C",
                has_client: true,
                projects: [blankProject({ name: "", description: "開発の詳細" })],
              }),
            ],
          }),
        ],
      }),
    );
    const project = payload.experiences[0].clients[0].projects[0];
    expect(project.name).toBe("");
    expect(project.description).toBe("開発の詳細");
  });
});

// ── 非IT企業の経歴 ────────────────────────────────────────────

describe("buildCareerPayload (non-IT experience)", () => {
  it("非ITは clients が空配列になり description が trim 保持される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            is_it_company: false,
            description: "  店舗運営を担当  ",
            clients: [blankClient({ name: "捨てられる", projects: [blankProject()] })],
          }),
        ],
      }),
    );
    expect(payload.experiences[0].is_it_company).toBe(false);
    expect(payload.experiences[0].description).toBe("店舗運営を担当");
    expect(payload.experiences[0].clients).toEqual([]);
  });

  it("非ITで description が空ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [blankExperience({ is_it_company: false, description: "   " })],
        }),
      ),
    ).toThrow(/詳細/);
  });

  it("ITの場合 description は空文字に正規化され clients が残る", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            is_it_company: true,
            description: "無視される",
            clients: [blankClient({ name: "顧客A", projects: [blankProject()] })],
          }),
        ],
      }),
    );
    expect(payload.experiences[0].description).toBe("");
    expect(payload.experiences[0].clients).toHaveLength(1);
  });
});

// ── 休暇エントリ ──────────────────────────────────────────────

describe("buildCareerPayload (vacation client)", () => {
  it("休暇は projects 空・name 空で vacation_* が trim 保持される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                is_vacation: true,
                vacation_start_date: " 2020-04 ",
                vacation_end_date: " 2021-03 ",
                vacation_description: " 育児休暇 ",
              }),
            ],
          }),
        ],
      }),
    );
    const client = payload.experiences[0].clients[0];
    expect(client.is_vacation).toBe(true);
    expect(client.name).toBe("");
    expect(client.projects).toEqual([]);
    expect(client.vacation_start_date).toBe("2020-04");
    expect(client.vacation_end_date).toBe("2021-03");
    expect(client.vacation_description).toBe("育児休暇");
  });

  it("休暇が継続中なら vacation_end_date は空文字に正規化される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [
          blankExperience({
            clients: [
              blankClient({
                is_vacation: true,
                vacation_start_date: "2020-04",
                vacation_end_date: "2021-03",
                vacation_is_current: true,
                vacation_description: "育児休暇",
              }),
            ],
          }),
        ],
      }),
    );
    expect(payload.experiences[0].clients[0].vacation_end_date).toBe("");
  });

  it("休暇で開始年月が空ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [
            blankExperience({
              clients: [
                blankClient({
                  is_vacation: true,
                  vacation_start_date: "",
                  vacation_description: "育児休暇",
                }),
              ],
            }),
          ],
        }),
      ),
    ).toThrow(/休暇の開始年月/);
  });

  it("休暇で継続中でなく終了年月が空ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [
            blankExperience({
              clients: [
                blankClient({
                  is_vacation: true,
                  vacation_start_date: "2020-04",
                  vacation_end_date: "",
                  vacation_is_current: false,
                }),
              ],
            }),
          ],
        }),
      ),
    ).toThrow(/休暇の終了年月/);
  });

  it("休暇で終了年月が開始年月より前ならエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          experiences: [
            blankExperience({
              clients: [
                blankClient({
                  is_vacation: true,
                  vacation_start_date: "2021-04",
                  vacation_end_date: "2020-03",
                }),
              ],
            }),
          ],
        }),
      ),
    ).toThrow(/開始日/);
  });

  it("中身が空の休暇エントリは除外される", () => {
    const payload = buildCareerPayload(
      baseState({
        experiences: [blankExperience({ clients: [blankClient({ is_vacation: true })] })],
      }),
    );
    expect(payload.experiences[0].clients).toEqual([]);
  });
});

// ── qualifications の境界 ────────────────────────────────────

describe("buildCareerPayload (qualifications)", () => {
  it("空欄の qualification は除外される", () => {
    const payload = buildCareerPayload(
      baseState({
        qualifications: [{ acquired_date: "", name: "" }],
      }),
    );
    expect(payload.qualifications).toEqual([]);
  });

  it("片方だけ埋まった qualification はエラー", () => {
    expect(() =>
      buildCareerPayload(
        baseState({
          qualifications: [{ acquired_date: "2024-01-01", name: "" }],
        }),
      ),
    ).toThrow(/資格/);
  });

  it("両方埋まった qualification は trim されて残る", () => {
    const payload = buildCareerPayload(
      baseState({
        qualifications: [{ acquired_date: " 2024-01-01 ", name: " 基本情報 " }],
      }),
    );
    expect(payload.qualifications).toEqual([{ acquired_date: "2024-01-01", name: "基本情報" }]);
  });
});
