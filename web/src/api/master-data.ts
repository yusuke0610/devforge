import { request } from "./client";
import { PATHS } from "./paths";
import type { MasterItem, TechStackMasterItem } from "./types";

export function getQualifications(): Promise<MasterItem[]> {
  return request<MasterItem[]>(PATHS.masterData.qualification);
}

export function getTechnologyStacks(): Promise<TechStackMasterItem[]> {
  return request<TechStackMasterItem[]>(PATHS.masterData.technologyStack);
}
