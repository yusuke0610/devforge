const assert = require("node:assert/strict");
const test = require("node:test");

const { buildCareerPayload } = require("../.test-dist/payloadBuilders.js");

test("buildCareerPayload trims data and keeps only non-empty technology stacks", () => {
  const payload = buildCareerPayload({
    full_name: "  山田 太郎  ",
    career_summary: "  職務要約テスト  ",
    self_pr: "  自己PRテスト  ",
    experiences: [
      {
        company: "  Example株式会社  ",
        business_description: "  SES事業  ",
        start_date: "2020-04",
        end_date: "",
        is_current: true,
        employee_count: "  300名  ",
        capital: "  1億円  ",
        clients: [
          {
            has_client: true,
            name: "  クライアントA  ",
            projects: [
              {
                name: "  プロジェクトA  ",
                start_date: "2020-04",
                end_date: "2021-03",
                is_current: false,
                role: "  メンバー  ",
                description: "  課題・行動・成果テスト  ",
                team: {
                  total: "  5  ",
                  members: [
                    { role: "SE", count: "3" },
                    { role: "PG", count: "2" },
                    { role: "  ", count: "  " }
                  ]
                },
                phases: ["要件定義", "開発", ""],
                technology_stacks: [
                  {
                    category: "framework",
                    name: "  FastAPI  "
                  },
                  {
                    category: "language",
                    name: "   "
                  }
                ]
              }
            ]
          }
        ]
      }
    ],
    qualifications: [
      {
        acquired_date: "2020-04-01",
        name: "応用情報技術者"
      },
      {
        acquired_date: "  ",
        name: "  "
      }
    ]
  });

  assert.equal(payload.full_name, "山田 太郎");
  assert.equal(payload.career_summary, "職務要約テスト");
  assert.equal(payload.self_pr, "自己PRテスト");
  assert.equal(payload.experiences.length, 1);
  assert.equal(payload.experiences[0].is_current, true);
  assert.equal(payload.experiences[0].business_description, "SES事業");
  assert.equal(payload.experiences[0].clients.length, 1);
  assert.equal(payload.experiences[0].clients[0].name, "クライアントA");
  assert.equal(payload.experiences[0].clients[0].projects.length, 1);
  assert.equal(payload.experiences[0].clients[0].projects[0].name, "プロジェクトA");
  assert.equal(payload.experiences[0].clients[0].projects[0].role, "メンバー");
  assert.equal(
    payload.experiences[0].clients[0].projects[0].description,
    "課題・行動・成果テスト"
  );
  assert.deepEqual(payload.experiences[0].clients[0].projects[0].technology_stacks, [
    {
      category: "framework",
      name: "FastAPI"
    }
  ]);
  assert.equal(payload.qualifications.length, 1);
  assert.deepEqual(payload.qualifications[0], {
    acquired_date: "2020-04-01",
    name: "応用情報技術者"
  });
});

test("buildCareerPayload throws when full_name is empty", () => {
  assert.throws(
    () =>
      buildCareerPayload({
        full_name: "",
        career_summary: "職務要約",
        self_pr: "自己PR",
        experiences: [],
        qualifications: []
      }),
    /氏名を入力してください。/
  );
});

test("buildCareerPayload throws when 離職で終了年月がない", () => {
  assert.throws(
    () =>
      buildCareerPayload({
        full_name: "山田 太郎",
        career_summary: "職務要約",
        self_pr: "自己PR",
        experiences: [
          {
            company: "Example株式会社",
            business_description: "SES事業",
            start_date: "2022-04",
            end_date: "",
            is_current: false,
            employee_count: "100名",
            capital: "5000万円",
            clients: []
          }
        ],
        qualifications: []
      }),
    /職務経歴の離職年月を入力するか、在職を選択してください。/
  );
});

test("buildCareerPayload throws when a 資格 is partially filled", () => {
  assert.throws(
    () =>
      buildCareerPayload({
        full_name: "山田 太郎",
        career_summary: "要約",
        self_pr: "自己PR",
        experiences: [],
        qualifications: [
          {
            acquired_date: "2020-04-01",
            name: ""
          }
        ]
      }),
    /資格は取得日と名称を両方入力してください。/
  );
});
