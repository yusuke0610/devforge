import { renderHook, act } from "@testing-library/react";
import { useState } from "react";
import { describe, it, expect } from "vitest";

import {
  blankCareerClient,
  blankCareerExperience,
  blankCareerProject,
} from "../../constants";
import type { CareerFormState } from "../../payloadBuilders";
import { useCareerExperienceMutators } from "./useCareerExperienceMutators";

/**
 * 経歴1件・取引先1件・プロジェクト1件を持つ標準フォームを作る。
 * 各テストはこの初期状態に対してミューテーターを適用し、結果の form state を検証する。
 */
function buildForm(overrides: Partial<CareerFormState> = {}): CareerFormState {
  return {
    full_name: "山田 太郎",
    email: "yamada@example.com",
    github_url: "",
    career_summary: "",
    self_pr: "",
    experiences: [
      {
        ...blankCareerExperience,
        company: "株式会社A",
        end_date: "2023-03",
        clients: [
          {
            ...blankCareerClient,
            name: "取引先A",
            has_client: true,
            projects: [{ ...blankCareerProject, name: "プロジェクトX" }],
          },
        ],
      },
    ],
    qualifications: [],
    ...overrides,
  };
}

/**
 * 実 React state（useState）越しにミューテーターを駆動するヘルパ。
 * 各ミューテーターは setForm の updater を介して state を更新するため、
 * act() 後の `form` で「画面操作の結果フォームがどう変わるか」を検証できる。
 */
function setup(initialForm: CareerFormState) {
  return renderHook(() => {
    const [form, setForm] = useState(initialForm);
    const mutators = useCareerExperienceMutators(form.experiences, setForm);
    return { form, mutators };
  });
}

describe("useCareerExperienceMutators", () => {
  describe("updateExperienceField", () => {
    it("is_current を true にすると end_date がクリアされる（在職中＝退職日なし）", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateExperienceField(0, "is_current", true);
      });
      expect(result.current.form.experiences[0].is_current).toBe(true);
      expect(result.current.form.experiences[0].end_date).toBe("");
    });

    it("is_current を false にしても end_date は保持される", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateExperienceField(0, "is_current", false);
      });
      expect(result.current.form.experiences[0].is_current).toBe(false);
      expect(result.current.form.experiences[0].end_date).toBe("2023-03");
    });

    it("通常フィールドは end_date を巻き込まずに更新される", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateExperienceField(0, "company", "株式会社B");
      });
      expect(result.current.form.experiences[0].company).toBe("株式会社B");
      expect(result.current.form.experiences[0].end_date).toBe("2023-03");
    });
  });

  describe("updateClientHasClient", () => {
    it("has_client を false にすると name がクリアされる", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateClientHasClient(0, 0, false);
      });
      expect(result.current.form.experiences[0].clients[0].has_client).toBe(false);
      expect(result.current.form.experiences[0].clients[0].name).toBe("");
    });

    it("has_client を true にしたときは name を保持する", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateClientHasClient(0, 0, true);
      });
      expect(result.current.form.experiences[0].clients[0].has_client).toBe(true);
      expect(result.current.form.experiences[0].clients[0].name).toBe("取引先A");
    });
  });

  describe("updateExperienceField (is_it_company)", () => {
    it("is_it_company を false にできる（非IT切替）", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateExperienceField(0, "is_it_company", false);
      });
      expect(result.current.form.experiences[0].is_it_company).toBe(false);
    });

    it("description フィールドを更新できる", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateExperienceField(0, "description", "店舗運営を担当");
      });
      expect(result.current.form.experiences[0].description).toBe("店舗運営を担当");
    });
  });

  describe("updateClientIsVacation", () => {
    it("休暇フラグを true/false に切り替える", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateClientIsVacation(0, 0, true);
      });
      expect(result.current.form.experiences[0].clients[0].is_vacation).toBe(true);
      act(() => {
        result.current.mutators.updateClientIsVacation(0, 0, false);
      });
      expect(result.current.form.experiences[0].clients[0].is_vacation).toBe(false);
    });
  });

  describe("updateClientVacationIsCurrent", () => {
    it("継続中を true にすると vacation_end_date がクリアされる", () => {
      const form = buildForm();
      form.experiences[0].clients[0] = {
        ...form.experiences[0].clients[0],
        is_vacation: true,
        vacation_start_date: "2020-04",
        vacation_end_date: "2021-03",
        vacation_is_current: false,
      };
      const { result } = setup(form);
      act(() => {
        result.current.mutators.updateClientVacationIsCurrent(0, 0, true);
      });
      const client = result.current.form.experiences[0].clients[0];
      expect(client.vacation_is_current).toBe(true);
      expect(client.vacation_end_date).toBe("");
    });

    it("継続中を false にしても vacation_end_date は保持される", () => {
      const form = buildForm();
      form.experiences[0].clients[0] = {
        ...form.experiences[0].clients[0],
        is_vacation: true,
        vacation_start_date: "2020-04",
        vacation_end_date: "2021-03",
        vacation_is_current: true,
      };
      const { result } = setup(form);
      act(() => {
        result.current.mutators.updateClientVacationIsCurrent(0, 0, false);
      });
      expect(result.current.form.experiences[0].clients[0].vacation_end_date).toBe("2021-03");
    });
  });

  describe("updateClientField (vacation fields)", () => {
    it("vacation_start_date / vacation_description を更新できる", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.updateClientField(0, 0, "vacation_start_date", "2020-04");
      });
      act(() => {
        result.current.mutators.updateClientField(0, 0, "vacation_description", "育児休暇");
      });
      const client = result.current.form.experiences[0].clients[0];
      expect(client.vacation_start_date).toBe("2020-04");
      expect(client.vacation_description).toBe("育児休暇");
    });
  });

  describe("removeExperience", () => {
    it("最後の1件は削除せず blank で置換する", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.removeExperience(0);
      });
      expect(result.current.form.experiences).toHaveLength(1);
      expect(result.current.form.experiences[0].company).toBe("");
    });

    it("複数あるときは該当 index を削除する", () => {
      const form = buildForm();
      form.experiences = [
        ...form.experiences,
        { ...blankCareerExperience, company: "株式会社B" },
      ];
      const { result } = setup(form);
      act(() => {
        result.current.mutators.removeExperience(0);
      });
      expect(result.current.form.experiences).toHaveLength(1);
      expect(result.current.form.experiences[0].company).toBe("株式会社B");
    });
  });

  describe("removeClient", () => {
    it("最後の1件は削除せず blank で置換する", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.removeClient(0, 0);
      });
      expect(result.current.form.experiences[0].clients).toHaveLength(1);
      expect(result.current.form.experiences[0].clients[0].name).toBe("");
    });

    it("複数あるときは該当 index を削除する", () => {
      const form = buildForm();
      form.experiences[0].clients = [
        ...form.experiences[0].clients,
        { ...blankCareerClient, name: "取引先B" },
      ];
      const { result } = setup(form);
      act(() => {
        result.current.mutators.removeClient(0, 0);
      });
      expect(result.current.form.experiences[0].clients).toHaveLength(1);
      expect(result.current.form.experiences[0].clients[0].name).toBe("取引先B");
    });
  });

  describe("removeProject", () => {
    it("最後の1件は削除せず blank で置換する", () => {
      const { result } = setup(buildForm());
      act(() => {
        result.current.mutators.removeProject(0, 0, 0);
      });
      const projects = result.current.form.experiences[0].clients[0].projects;
      expect(projects).toHaveLength(1);
      expect(projects[0].name).toBe("");
    });

    it("複数あるときは該当 index を削除する", () => {
      const form = buildForm();
      form.experiences[0].clients[0].projects = [
        ...form.experiences[0].clients[0].projects,
        { ...blankCareerProject, name: "プロジェクトY" },
      ];
      const { result } = setup(form);
      act(() => {
        result.current.mutators.removeProject(0, 0, 0);
      });
      const projects = result.current.form.experiences[0].clients[0].projects;
      expect(projects).toHaveLength(1);
      expect(projects[0].name).toBe("プロジェクトY");
    });
  });

  describe("onProjectSave", () => {
    it("projIndex が null のときは末尾に追加する", () => {
      const { result } = setup(buildForm());
      const newProject = { ...blankCareerProject, name: "新規プロジェクト" };
      act(() => {
        result.current.mutators.onProjectSave(0, 0, null, newProject);
      });
      const projects = result.current.form.experiences[0].clients[0].projects;
      expect(projects).toHaveLength(2);
      expect(projects[1].name).toBe("新規プロジェクト");
    });

    it("projIndex を指定したときは該当プロジェクトを置換する", () => {
      const { result } = setup(buildForm());
      const edited = { ...blankCareerProject, name: "編集済プロジェクト" };
      act(() => {
        result.current.mutators.onProjectSave(0, 0, 0, edited);
      });
      const projects = result.current.form.experiences[0].clients[0].projects;
      expect(projects).toHaveLength(1);
      expect(projects[0].name).toBe("編集済プロジェクト");
    });
  });

  describe("getProjectCount", () => {
    it("該当 client の現在のプロジェクト数を返す", () => {
      const form = buildForm();
      form.experiences[0].clients[0].projects = [
        ...form.experiences[0].clients[0].projects,
        { ...blankCareerProject, name: "プロジェクトY" },
      ];
      const { result } = setup(form);
      expect(result.current.mutators.getProjectCount(0, 0)).toBe(2);
    });

    it("存在しない座標では 0 を返す", () => {
      const { result } = setup(buildForm());
      expect(result.current.mutators.getProjectCount(9, 9)).toBe(0);
    });
  });
});
