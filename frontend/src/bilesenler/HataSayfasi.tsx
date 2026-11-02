import { Link, useRouteError } from "react-router-dom";

/** Yönlendirici `errorElement`'i: bir sayfa çizilirken fırlayan beklenmeyen hata için. */
export function HataSayfasi() {
  const hata = useRouteError();
  const ayrinti = hata instanceof Error ? hata.message : null;
  return (
    <main role="alert" className="flex min-h-screen flex-col items-start gap-3 p-6">
      <h1 className="text-xl font-semibold">Beklenmeyen bir hata oluştu</h1>
      <p className="text-sm text-muted-foreground">Sayfa gösterilemedi. Ana sayfaya dönüp tekrar deneyebilirsiniz.</p>
      {ayrinti && <pre className="max-w-full overflow-x-auto rounded-md bg-muted p-2 text-xs">{ayrinti}</pre>}
      <Link to="/" className="text-sm text-primary underline-offset-4 hover:underline">
        Ana sayfaya dön
      </Link>
    </main>
  );
}
