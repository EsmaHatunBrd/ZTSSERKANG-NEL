import { http, HttpResponse } from "msw";
import type { SenaryoTeklifSatiri } from "@/api/tipler";
import type { ExcelTamYaniti } from "@/api/tipler";
import { importOzeti, senaryoTeklifleri } from "../fikstur/aktar";

const T = "*/api/v1";

export interface YakalananImport {
  /** İstek başlığı Content-Type (multipart/form-data; boundary=...). */
  icerikTuru: string;
}

/**
 * jsdom FormData + undici birleşiminde MSW gövdeyi (formData/text) okuyamaz (akış erken kapanır);
 * bu yüzden gönderilen alanlar `FormData.prototype.append` çağrılarından yakalanır, istek ise yalnızca başlığıyla doğrulanır.
 */
export function formAlanlariniYakala(): { alanlar: Record<string, string | File>; geri: () => void } {
  const alanlar: Record<string, string | File> = {};
  const asil = FormData.prototype.append;
  FormData.prototype.append = function (this: FormData, ad: string, deger: string | Blob, dosyaAdi?: string) {
    alanlar[ad] = deger as string | File;
    return dosyaAdi === undefined ? asil.call(this, ad, deger as string) : asil.call(this, ad, deger as Blob, dosyaAdi);
  } as typeof FormData.prototype.append;
  return {
    alanlar,
    geri: () => {
      FormData.prototype.append = asil;
    },
  };
}

/** POST /import/excel-tam başarılı; istek başlıklarını `yakala`ya yazar. */
export function excelTamBasarili(yakala?: YakalananImport[], yanit: ExcelTamYaniti = importOzeti) {
  return http.post(`${T}/import/excel-tam`, ({ request }) => {
    yakala?.push({ icerikTuru: request.headers.get("content-type") ?? "" });
    return HttpResponse.json(yanit);
  });
}

export function excelTamHatasi(mesaj = "Dosya beklenen çalışma kitabı yapısında değil", alanlar: Record<string, unknown> = { sayfa: "Maliyet" }) {
  return http.post(`${T}/import/excel-tam`, () =>
    HttpResponse.json({ hata: "dogrulama", mesaj, alanlar }, { status: 422 }),
  );
}

export interface TeklifIstekleri {
  /** GET /teklifler istek sorgu parametreleri (sırayla). */
  liste: Record<string, string>[];
  durumlar: { id: string; govde: { durum: string } }[];
}

/**
 * Senaryo geneli teklif ucu: durum (tam eşleşme) ve müşteri (içerir, büyük/küçük harf duyarsız) süzer,
 * sayfa/boyut ile dilimler. `kayit` verilirse istekleri toplar.
 */
export function tekliflerIsleyicileri(kayit?: TeklifIstekleri, veri: SenaryoTeklifSatiri[] = senaryoTeklifleri) {
  const kaynak = veri.map((x) => ({ ...x }));
  return [
    http.get(`${T}/teklifler`, ({ request }) => {
      const q = new URL(request.url).searchParams;
      kayit?.liste.push(Object.fromEntries(Array.from(q as unknown as Iterable<[string, string]>)));
      const durum = q.get("durum");
      const musteri = (q.get("musteri") ?? "").toLocaleLowerCase("tr");
      const sayfa = Number(q.get("sayfa") ?? 1);
      const boyut = Number(q.get("boyut") ?? 50);
      const suzulen = kaynak.filter(
        (x) => (!durum || x.durum === durum) && (!musteri || (x.musteri ?? "").toLocaleLowerCase("tr").includes(musteri)),
      );
      return HttpResponse.json({ kayitlar: suzulen.slice((sayfa - 1) * boyut, sayfa * boyut), toplam: suzulen.length });
    }),
    http.patch(`${T}/teklifler/:id/durum`, async ({ request, params }) => {
      const g = (await request.json()) as { durum: string };
      kayit?.durumlar.push({ id: String(params.id), govde: g });
      const t = kaynak.find((x) => x.teklif_id === Number(params.id));
      if (t) t.durum = g.durum;
      return HttpResponse.json(t ?? {});
    }),
  ];
}

export function uyarilarIsleyici(kayitlar: { urun_kodu: string; uyari: string }[]) {
  return http.get(`${T}/uyarilar`, () => HttpResponse.json({ kayitlar, toplam: kayitlar.length }));
}

/** Elle reçete satırı gönderimini yakalar. */
export function receteEkleYakala(yakala: { kod: string; senaryo: string | null; govde: unknown }[]) {
  return http.post(`${T}/urunler/:kod/recete`, async ({ params, request }) => {
    yakala.push({
      kod: String(params.kod),
      senaryo: new URL(request.url).searchParams.get("senaryo"),
      govde: await request.json(),
    });
    return HttpResponse.json({ id: 21, versiyon: 4, satir_sayisi: 1 }, { status: 201 });
  });
}
