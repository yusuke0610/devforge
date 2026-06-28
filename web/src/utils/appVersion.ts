/** ビルド時に注入されるアプリバージョン（git tag 由来 / 未注入時は dev）。 */
export const APP_VERSION: string = import.meta.env.VITE_APP_VERSION ?? "dev";
