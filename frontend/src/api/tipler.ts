/**
 * Yanıt tipleri. Kaynak `sema.d.ts`'tir (backend `/openapi.json`'dan `npm run api:tipler` ile üretilir);
 * burada yalnızca eski/kısa adlar için takma adlar vardır. Elle tip tanımlanmaz: backend `response_model` değişince
 * şema yeniden üretilir ve tsc uyumsuzlukları gösterir.
 * Tutarlar daima metindir (Decimal ile işlenir).
 */
import type { components } from "./sema";

export type Sema = components["schemas"];

/** Sayfalı/kayıt listesi biçimi; somut liste yanıtlarının ortak şekli (test verileri için). */
export interface Liste<T> {
  kayitlar: T[];
  toplam: number;
}

/** `urun_sayisi`: çalışmaya üye (aktif reçetesi olan) ürün sayısı (Faz 5c). */
export type Senaryo = Sema["SenaryoCikis"];
export type DashboardSatiri = Sema["DashboardSatiri"];
export type UretimHedefi = Sema["UretimHedefiCikis"];
/** `senaryoda`: ürünün seçili çalışmada aktif reçetesi var mı; yalnız `GET /urunler/{kod}?senaryo=` yanıtında (Faz 5c). */
export type Urun = Sema["UrunCikis"];
/** `marka` boş bırakılırsa yeni üründe sunucu addan türetir. */
export type UrunGiris = Sema["UrunGiris"];
export type ReceteSatiri = Sema["ReceteSatiriFireli"];
/** Reçetesiz üründe `GET recete` 404 yerine `{id: null, versiyon: 0, satirlar: []}` döner (Faz 5c). */
export type Recete = Sema["ReceteCikis"];
export type ReceteVersiyonu = Sema["ReceteVersiyonu"];
export type HesapSatiri = Sema["HesapSatiri"];
export type Toplamlar = Sema["HesapToplamlari"];
export type Fiyatlar = Sema["HesapFiyatlari"];
export type HesapYaniti = Sema["HesapYaniti"];
/** `HesapYaniti`'nın eski adı. */
export type MaliyetSonucu = HesapYaniti;
export type KayitliHesapOzeti = Sema["HesapOzeti"];
export type KayitliHesap = Sema["HesapKayitCikis"];
export type HesapKaydiYaniti = Sema["HesapKaydiYaniti"];
export type Teklif = Sema["TeklifCikis"];
export type Malzeme = Sema["MalzemeSatiri"];
export type FiyatKaydi = Sema["FiyatKaydi"];
export type ParametreTanimi = Sema["ParametreTanimi"];
/** GET /parametreler: anahtar -> değer (metin). */
export type ParametreDegerleri = { [anahtar: string]: string };
export type ParametreKaydi = Sema["ParametreKaydi"];
export type GiderAnahtari = Sema["GiderAnahtari"];
export type GiderHavuzu = Sema["GiderHavuzuCikis"];
export type HavuzListesi = Sema["GiderHavuzlariCikis"];
export type Ambalaj = Sema["AmbalajCikis"];
export type FireKurali = Sema["FireKuraliCikis"];
export type MalzemeGrubu = Sema["MalzemeGrubuCikis"];
export type Uyari = Sema["UyariSatiri"];
export type Degisiklik = Sema["DegisiklikKaydi"];
export type FiyatOnizleme = Sema["FiyatListesiOnizleme"];
export type FiyatUygulamaYaniti = Sema["FiyatListesiUygulama"];
export type ExcelTamYaniti = Sema["ImportOzeti"];
export type HataGovdesi = Sema["HataGovdesi"];

// Faz 4 Görev 9: senaryo geneli teklif listesi ve ambalaj kaydı gövdesi.
export type SenaryoTeklifSatiri = Sema["SenaryoTeklifSatiri"];
export type SenaryoTeklifListesi = Sema["SenaryoTeklifListesi"];
export type AmbalajKaydiGiris = Sema["AmbalajKaydiGiris"];
export type HavuzGiris = Sema["HavuzGiris"];

// Faz 4b: Excel blokları (üretim bilgileri, parametre özeti), Üretim Adetleri, ambalaj özeti, metin parametreler.
export type UretimBilgisi = Sema["UretimBilgisiCikis"];
export type ParametreOzeti = Sema["ParametreOzetiCikis"];
export type KapasiteKaydi = Sema["KapasiteCikis"];
export type KapasiteListesi = Sema["KapasiteListesi"];
export type KapasiteGiris = Sema["KapasiteGiris"];
export type AmbalajOzeti = Sema["AmbalajOzeti"];
export type AmbalajTuruOzeti = Sema["AmbalajTuruOzeti"];
export type KapakOzeti = Sema["KapakOzeti"];
export type MetinParametre = Sema["MetinParametreCikis"];
export type MetinParametreListesi = Sema["MetinParametreListesi"];
export type MetinParametreGiris = Sema["MetinParametreGiris"];

// Faz 4c: tek atomik kayıt (POST /urunler/{kod}/kaydet).
export type TopluKaydetGiris = Sema["TopluKaydetGiris"];
export type TopluKaydetCikis = Sema["TopluKaydetCikis"];
export type HesaplaOverride = Sema["OverrideGiris"];
export type SatirOverride = Sema["SatirOverride"];

export type SatisKaydi = Sema["SatisCikis"];
export type SatisGirisi = Sema["SatisGiris"];
export type SatisYuklemeOzeti = Sema["SatisYuklemeOzeti"];
export type SatisYuklemeHatasi = Sema["SatisYuklemeHatasi"];

// Faz 5: Veri Aktar (/aktarim/...).
export type AktarimOnizleUretim = Sema["AktarimOnizleUretim"];
export type AktarimUygulaUretim = Sema["AktarimUygulaUretim"];
export type AktarimOnizleSatinAlma = Sema["AktarimOnizleSatinAlma"];
export type AktarimUygulaSatinAlma = Sema["AktarimUygulaSatinAlma"];
export type AktarimOnizleGider = Sema["AktarimOnizleGider"];
export type AktarimUygulaGider = Sema["AktarimUygulaGider"];
export type AktarimOnizleRecete = Sema["AktarimOnizleRecete"];
export type AktarimUygulaRecete = Sema["AktarimUygulaRecete"];
export type ReceteAktarimSayfasi = Sema["ReceteAktarimSayfasi"];

// Faz 5: karşılaştırma ekranları (/karsilastirma/...).
export type UrunKarsilastirma = Sema["UrunKarsilastirmaCikis"];
export type GecenYil = Sema["GecenYilCikis"];
export type GecenYilPb = Sema["GecenYilPb"];
export type EnflasyonPb = Sema["EnflasyonPb"];
export type UretimEtkisi = Sema["UretimEtkisiCikis"];
export type AileOzeti = Sema["AileCikis"];
export type AileKarsilastirma = Sema["AileKarsilastirmaCikis"];
export type AileSatiri = Sema["AileSatiriCikis"];

// Faz 5c: yeni çalışma (boş / kopya), senaryo düzenleme ve silme.
export type SenaryoKopyaSecimi = Sema["SenaryoKopyaSecimleri"];
export type SenaryoKopyaGiris = Sema["SenaryoKopyaGiris"];
export type KopyalananSayilar = Sema["SenaryoKopyaSayilari"];
export type SenaryoKopyaCikis = Sema["SenaryoKopyaCikis"];
export type SenaryoGuncelleGiris = Sema["SenaryoGuncelleGiris"];

// Faz 6: Bütçe vs Gerçekleşen (iki senaryonun ürün bazında kıyası).
export type BgSenaryo = Sema["BgKiyasSenaryo"];
export type BgDeger = Sema["BgKiyasDegeri"];
export type BgAlanlar = Sema["BgKiyasAlanlari"];
export type BgSatir = Sema["BgKiyasSatiri"];
export type BgListe = Sema["BgKiyasListesi"];
export type BgUrun = Sema["BgKiyasUrunCikis"];
export type BgReceteSatiri = Sema["BgKiyasReceteSatiri"];
export type BgAyristirma = Sema["BgKiyasAyristirma"];

// D7: Veri Kontrolü (çalışmanın veri sorunları tek listede).
export type Tutarlilik = Sema["TutarlilikCikis"];
export type TutarlilikKontrolu = Sema["TutarlilikKontrolu"];
export type ListePazari = "yurtici" | "yurtdisi";
export type ListeGecmisSatiri = Sema["ListeGecmisSatiri"];
export type ListeCalismaSatiri = Sema["ListeCalismaSatiri"];
export type ListeCalismasi = Sema["ListeCalismasi"];
export type ListeFiyatiGiris = Sema["ListeFiyatiGiris"];
export type ListeYilSatiri = Sema["ListeYilSatiri"];
export type AnalizSatiri = Sema["AnalizSatiri"];
export type AnalizOzeti = Sema["AnalizOzeti"];
export type SmmDonem = Sema["SmmDonemCikis"];
export type SmmStokSatiri = Sema["SmmStokSatiri"];
export type SmmStokTablosu = Sema["SmmStokTablosu"];
export type SmmUretimMaliyeti = Sema["SmmUretimMaliyeti"];
export type SmmAsamaUrunu = Sema["SmmAsamaUrunu"];
export type SmmUrunRecetesi = Sema["SmmUrunRecetesi"];
export type SmmDagitim = Sema["SmmDagitim"];
export type SmmSarfFarki = Sema["SmmSarfFarki"];
export type SmmSarfSatiri = Sema["SmmSarfSatiri"];
export type SmmOzeti = Sema["SmmOzeti"];
export type SmmReceteListesi = Sema["SmmReceteListesi"];
export type SmmReceteUrunu = Sema["SmmReceteUrunu"];
export type SmmReceteDetayi = Sema["SmmReceteDetayi"];
export type SmmAnaReceteOnizleme = Sema["SmmAnaReceteOnizleme"];
export type SmmReceteKiyas = Sema["SmmReceteKiyas"];
export type SmmYeniDonem = Sema["SmmYeniDonemCikis"];
export type SmmSure = Sema["SmmSure"];
export type SmmVeriDurumu = Sema["SmmVeriDurumu"];

export type KurRiskiSatiri = Sema["KurRiskiSatiri"];
export type KurRiskiSonucu = Sema["KurRiskiCikis"];
export type KarlilikBolgesi = "yuksek_adet_yuksek_marj" | "yuksek_adet_dusuk_marj" | "dusuk_adet_yuksek_marj" | "dusuk_adet_dusuk_marj";
export type KarlilikSatiri = Sema["KarlilikSatiri"];
export type KarlilikSonucu = Sema["KarlilikCikis"];

export type HedefFiyatSatiri = Sema["HedefFiyatSatiri"];
export type HedefFiyatSonucu = Sema["HedefFiyatCikis"];

// Stokta kalan (stok devri): ürün başına isteğe bağlı, çalışmaya bağlı kayıt. Oranlar 0.40 = %40.
/** Kayıt yoksa alanlar null, `stok_etkisi` false. */
export type StokDevri = Sema["StokDevriCikis"];
export type StokDevriGiris = Sema["StokDevriGiris"];
export type StokDevriSatiri = Sema["StokDevriSatiri"];
export type StokDevriListesi = Sema["StokDevriListesi"];
export type AktarimOnizleStokDevri = Sema["StokDevriOnizle"];
export type AktarimUygulaStokDevri = Sema["StokDevriUygula"];
export type StokDevriAktarimSatiri = Sema["StokDevriAktarimSatiri"];

// Dalga 4 (12.11.2026): fiyat eğilimi (analiz önerisi 9) ve tek sayfa yönetim özeti (15). Yüzdeler metin, 2 basamak.
export type FiyatEgilimiSatiri = Sema["FiyatEgilimiSatiri"];
export type FiyatEgilimiSonucu = Sema["FiyatEgilimiCikis"];
export type YonetimOzeti = Sema["YonetimOzetiCikis"];
