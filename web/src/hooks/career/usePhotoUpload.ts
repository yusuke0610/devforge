/**
 * 証明写真のアップロード・リサイズ処理を提供するカスタムフック。
 * 選択した画像を 450×600 px に変換して Base64 文字列として返す。
 */
export function usePhotoUpload(
  onPhotoChange: (photo: string) => void,
) {
  /**
   * ファイル input の change イベントを受け取り、
   * Canvas でリサイズした後に Base64 文字列として親へ通知する。
   */
  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        canvas.width = 450;
        canvas.height = 600;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(img, 0, 0, 450, 600);
          const resized = canvas.toDataURL("image/jpeg", 0.9);
          onPhotoChange(resized);
        }
      };
      img.src = reader.result as string;
    };
    reader.readAsDataURL(file);
  };

  return { handleFileChange };
}
