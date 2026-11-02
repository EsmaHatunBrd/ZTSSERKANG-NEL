import { Link } from "react-router-dom";

/** Eşleşmeyen adresler için (`*` rotası): Kabuk içinde, menü görünür kalır. */
export function SayfaBulunamadi() {
  return (
    <section className="flex flex-col items-start gap-3 p-4">
      <h1 className="text-xl font-semibold">Sayfa bulunamadı</h1>
      <p className="text-sm text-muted-foreground">Aradığınız adres yok ya da taşınmış olabilir.</p>
      <Link to="/" className="text-sm text-primary underline-offset-4 hover:underline">
        Ana sayfaya dön
      </Link>
    </section>
  );
}
