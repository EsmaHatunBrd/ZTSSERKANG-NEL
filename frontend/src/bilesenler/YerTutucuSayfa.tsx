export function YerTutucuSayfa({ baslik }: { baslik: string }) {
  return (
    <section>
      <h1 className="text-2xl font-semibold">{baslik}</h1>
      <p className="mt-2 text-sm text-muted-foreground">Bu sayfa hazırlanıyor.</p>
    </section>
  );
}
